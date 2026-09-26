import type { Page, Request, Route, WebSocketRoute } from '@playwright/test';

// A stand-in for every service the web app talks to, served from inside the
// browser via Playwright routing. Nothing reaches the hosted Supabase project,
// the Judge0 wrapper or the OCR service; a request the fake does not recognise
// fails the test instead of leaking out.

export interface TestCaseRow {
  test_code: string;
  test_input: string;
  expected_output: string;
}

export interface QuestionRow {
  id: string;
  question_name: string;
  question_text?: string;
  question_type: 'function' | 'program';
  model_answer: string;
  test_cases: TestCaseRow[];
  created_at: string;
  // Validated flag (20260926000300_restore_question_can_publish.sql).
  can_publish?: boolean;
}

export interface SubmissionRow {
  id: string;
  image_url: string;
  captured_at: string;
  status: string;
  topic: string | null;
  student_name: string | null;
  extracted_text: string | null;
  verified_text: string | null;
  question_id: string | null;
  grading_results: unknown[] | null;
  passed_test_cases: number | null;
  total_test_cases: number | null;
  score_percent: number | null;
  graded_at: string | null;
  grading_revision: number;
  // Programs 2..n of a paper (20260923000000_add_submission_answers.sql).
  answers: unknown[];
  // The phone's photo verdict (20260926000200_add_submission_gate_result.sql).
  gate_result: string | null;
}

// One verified program on a paper (20260926000600_add_submission_programs).
export interface ProgramRow {
  id: string;
  submission_id: string;
  position: number;
  question_id: string;
  verified_text: string;
  grading_results: unknown[];
  passed_test_cases: number | null;
  total_test_cases: number | null;
  score_percent: number | null;
  graded_at: string | null;
  grading_revision: number;
}

export interface SectionRow {
  id: string;
  name: string;
  position: number;
}

export interface SectionItemRow {
  section_id: string;
  question_id: string;
  number: number;
}

export interface Judge0Run {
  source_code: string;
  stdin: string;
}

export interface Judge0Result {
  stdout?: string;
  stderr?: string;
  compile_output?: string;
  status: { id: number; description: string };
}

export type Judge0Handler = (run: Judge0Run) => Judge0Result;

export interface OcrRequest {
  image_url: string;
  submission_id: string;
}

// Returns the cleaned text, or null to make the OCR service fail.
export type OcrHandler = (request: OcrRequest) => string | null;

// A postgres_changes binding the page subscribed to, with the id the fake
// server assigned it in the join reply.
interface RealtimeBinding {
  topic: string;
  id: number;
  event: string;
  schema: string;
  table: string;
}

export interface RecordedRequest {
  method: string;
  url: URL;
  body: any;
}

const SUPABASE_ORIGIN = 'https://cvtshfshqccuncamvnkl.supabase.co';
const JUDGE0_API = 'http://127.0.0.1:8001/api/judge0';
const OCR_SERVER = 'http://localhost:8000';
const OCR_API = `${OCR_SERVER}/api/ocr`;

// A 1x1 grey PNG, so submission cards render an image without any network.
export const PLACEHOLDER_IMAGE =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==';

export const accepted = (stdout: string): Judge0Result => ({
  stdout,
  status: { id: 3, description: 'Accepted' },
});

export const compileError = (message: string): Judge0Result => ({
  compile_output: message,
  status: { id: 6, description: 'Compilation Error' },
});

export class FakeBackend {
  readonly questions: QuestionRow[] = [];
  readonly submissions = new Map<string, SubmissionRow>();
  readonly programs: ProgramRow[] = [];
  readonly sections: SectionRow[] = [];
  readonly sectionItems: SectionItemRow[] = [];
  readonly requests: RecordedRequest[] = [];
  readonly unexpected: string[] = [];

  // How the fake Judge0 "executes" one run. Tests replace it to decide the
  // output for each test case.
  judge0: Judge0Handler = () => accepted('');
  // Makes the whole Judge0 wrapper answer with this HTTP status, e.g. 502
  // when the VM is down.
  judge0FailureStatus: number | null = null;
  // Runs just before save_submission_grade, e.g. to simulate another teacher
  // editing the submission while grading is in flight.
  beforeGradeSave?: (submission: SubmissionRow) => void;
  // Same, for save_program_grade.
  beforeProgramGradeSave?: (program: ProgramRow) => void;
  ocr: OcrHandler = () => null;

  private socket?: WebSocketRoute;
  private realtimeBindings: RealtimeBinding[] = [];
  private nextQuestionNumber = 1;
  private nextSectionNumber = 1;
  private nextProgramNumber = 1;

  // True once the page's submissions channel has joined, so pushed changes
  // will reach it.
  get realtimeSubscribed(): boolean {
    return this.realtimeBindings.some((binding) => binding.table === 'submissions');
  }

  addQuestion(question: Partial<QuestionRow> & Pick<QuestionRow, 'id' | 'question_name'>) {
    const row: QuestionRow = {
      question_type: 'program',
      model_answer: '',
      test_cases: [],
      created_at: new Date().toISOString(),
      ...question,
    };
    this.questions.push(row);
    return row;
  }

  addSubmission(submission: Partial<SubmissionRow> & Pick<SubmissionRow, 'id'>) {
    const row: SubmissionRow = {
      image_url: PLACEHOLDER_IMAGE,
      captured_at: new Date().toISOString(),
      status: 'pending',
      topic: null,
      student_name: null,
      extracted_text: null,
      verified_text: null,
      question_id: null,
      grading_results: null,
      passed_test_cases: null,
      total_test_cases: null,
      score_percent: null,
      graded_at: null,
      grading_revision: 0,
      answers: [],
      gate_result: null,
      ...submission,
    };
    this.submissions.set(row.id, row);
    // Like the migration's copy step: verified code with a question is
    // Program 1, keeping any grade the page already has.
    if (row.question_id && row.verified_text?.trim()) {
      this.addProgram(row.id, 1, row.question_id, row.verified_text, {
        grading_results: row.grading_results ?? [],
        passed_test_cases: row.passed_test_cases,
        total_test_cases: row.total_test_cases,
        score_percent: row.score_percent,
        graded_at: row.graded_at,
      });
      // The grade now lives on the program; the page keeps none
      // (20260926000900).
      Object.assign(row, {
        grading_results: [],
        passed_test_cases: null,
        total_test_cases: null,
        score_percent: null,
        graded_at: null,
      });
    }
    return row;
  }

  // Program 2+ on a paper, as the review's program tabs save it.
  addExtraProgram(submissionId: string, position: number, questionId: string, code: string) {
    return this.addProgram(submissionId, position, questionId, code);
  }

  programsOf(submissionId: string): ProgramRow[] {
    return this.programs
      .filter((program) => program.submission_id === submissionId)
      .sort((a, b) => a.position - b.position);
  }

  private addProgram(
    submissionId: string,
    position: number,
    questionId: string,
    code: string,
    grade: Partial<ProgramRow> = {},
  ) {
    const row: ProgramRow = {
      id: `00000000-0000-4000-a000-${String(this.nextProgramNumber++).padStart(12, '0')}`,
      submission_id: submissionId,
      position,
      question_id: questionId,
      verified_text: code,
      grading_results: [],
      passed_test_cases: null,
      total_test_cases: null,
      score_percent: null,
      graded_at: null,
      grading_revision: 0,
      ...grade,
    };
    this.programs.push(row);
    return row;
  }

  addSection(name: string, position = this.sections.length) {
    const row: SectionRow = {
      id: `00000000-0000-4000-9000-${String(this.nextSectionNumber++).padStart(12, '0')}`,
      name,
      position,
    };
    this.sections.push(row);
    return row;
  }

  // Puts a question in a section with a number (Nikko's section tables).
  addSectionItem(sectionId: string, questionId: string, number: number) {
    const row: SectionItemRow = { section_id: sectionId, question_id: questionId, number };
    this.sectionItems.push(row);
    return row;
  }

  requestsTo(method: string, pathPart: string): RecordedRequest[] {
    return this.requests.filter(
      (request) =>
        request.method === method && request.url.pathname.includes(pathPart),
    );
  }

  async install(page: Page) {
    // Realtime is served by the fake too; the socket never reaches the real
    // project. Changes reach the page only when a test calls pushInsert().
    await page.routeWebSocket(/\/realtime\/v1\/websocket/, (socket) =>
      this.handleRealtime(socket),
    );

    await page.route(`${SUPABASE_ORIGIN}/**`, (route) => this.handleSupabase(route));
    await page.route(`${JUDGE0_API}/**`, (route) => this.handleJudge0(route));
    await page.route(`${OCR_API}/**`, (route) => this.handleOcr(route));
    // The list polls the OCR server's health for its automatic-extraction
    // state; here it is always off.
    await page.route(`${OCR_SERVER}/`, (route) =>
      this.json(route, {
        status: 'ok',
        auto_extract: { enabled: false, since: null, failed: [] },
      }),
    );
  }

  // What the mobile app's upload looks like to the web page: a new row, then
  // a realtime INSERT event for it.
  pushInsert(submission: Partial<SubmissionRow> & Pick<SubmissionRow, 'id'>) {
    const row = this.addSubmission(submission);
    if (!this.socket) throw new Error('The page has not opened a realtime socket');
    const matching = this.realtimeBindings.filter(
      (binding) => binding.table === 'submissions' && binding.event === 'INSERT',
    );
    for (const topic of new Set(matching.map((binding) => binding.topic))) {
      const ids = matching
        .filter((binding) => binding.topic === topic)
        .map((binding) => binding.id);
      this.sendRealtime(null, null, topic, 'postgres_changes', {
        ids,
        data: {
          schema: 'public',
          table: 'submissions',
          commit_timestamp: new Date().toISOString(),
          type: 'INSERT',
          record: row,
          columns: Object.keys(row).map((name) => ({ name, type: 'text' })),
          errors: null,
        },
      });
    }
    return row;
  }

  // ── Realtime (Phoenix protocol, vsn 2.0.0 array frames) ──

  private handleRealtime(socket: WebSocketRoute) {
    this.socket = socket;
    this.realtimeBindings = [];
    socket.onMessage((message) => {
      if (typeof message !== 'string') return;
      const [joinRef, ref, topic, event, payload] = JSON.parse(message);
      let response: Record<string, unknown> = {};

      if (event === 'phx_join') {
        // Echo each requested postgres_changes filter back with an id, as the
        // server does; the client drops the channel if they do not match.
        const requested: Array<Omit<RealtimeBinding, 'topic' | 'id'>> =
          payload?.config?.postgres_changes ?? [];
        const bindings = requested.map((filter, index) => ({
          ...filter,
          topic,
          id: this.realtimeBindings.length + index + 1,
        }));
        this.realtimeBindings.push(...bindings);
        response = {
          postgres_changes: bindings.map(({ topic: _topic, ...filter }) => filter),
        };
      } else if (event === 'phx_leave') {
        this.realtimeBindings = this.realtimeBindings.filter(
          (binding) => binding.topic !== topic,
        );
      }
      if (ref !== null) {
        this.sendRealtime(joinRef, ref, topic, 'phx_reply', { status: 'ok', response });
      }
    });
  }

  private sendRealtime(
    joinRef: string | null,
    ref: string | null,
    topic: string,
    event: string,
    payload: unknown,
  ) {
    this.socket?.send(JSON.stringify([joinRef, ref, topic, event, payload]));
  }

  // ── OCR service ──────────────────────────────────────────

  private async handleOcr(route: Route) {
    const request = route.request();
    const url = new URL(request.url());
    this.record(request, url);

    if (request.method() === 'OPTIONS') {
      return route.fulfill({ status: 204, headers: cors() });
    }
    if (!url.pathname.endsWith('/extract-from-url')) {
      return this.reject(route, `Unhandled OCR request ${url.pathname}`);
    }
    const body = request.postDataJSON() as OcrRequest;
    const text = this.ocr(body);
    if (text === null) {
      return this.json(route, { detail: 'OCR failed' }, 500);
    }
    return this.json(route, {
      submission_id: body.submission_id,
      cleaned_text: text,
    });
  }

  // ── Supabase ─────────────────────────────────────────────

  private async handleSupabase(route: Route) {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    this.record(request, url);

    if (method === 'OPTIONS') return route.fulfill({ status: 204, headers: cors() });

    const path = url.pathname;
    if (method === 'GET' && path === '/rest/v1/questions') {
      return this.json(route, [...this.questions].reverse());
    }
    if (method === 'POST' && path === '/rest/v1/questions') {
      const [question] = request.postDataJSON() as Array<Omit<QuestionRow, 'id' | 'created_at'>>;
      const row = this.addQuestion({
        ...question,
        id: `00000000-0000-4000-8000-${String(this.nextQuestionNumber++).padStart(12, '0')}`,
      });
      return this.json(route, this.wantsObject(request) ? row : [row], 201);
    }
    // Editing a question (Nikko, 20260926000400_allow_question_updates.sql).
    if (method === 'PATCH' && path === '/rest/v1/questions') {
      const changes = request.postDataJSON() as Partial<QuestionRow>;
      const matched = filterRows(this.questions, url);
      for (const row of matched) {
        // Mirrors 20260926000800: changing what runs clears can_publish,
        // even when the same update sends true.
        const contentChanged = (['model_answer', 'test_cases', 'question_type'] as const).some(
          (key) => key in changes && JSON.stringify(changes[key]) !== JSON.stringify(row[key]),
        );
        Object.assign(row, changes);
        if (contentChanged) row.can_publish = false;
      }
      const body = this.wantsObject(request) ? (matched[0] ?? null) : matched;
      return this.json(route, body);
    }
    // countGradedPapers() reads the programs graded against a question.
    if (method === 'GET' && path === '/rest/v1/submission_programs') {
      return this.json(route, filterRows(this.programs, url));
    }
    if (method === 'GET' && path === '/rest/v1/submissions') {
      const rows = this.filterSubmissions(url)
        .sort((a, b) => Date.parse(b.captured_at) - Date.parse(a.captured_at))
        .map((row) => this.withQuestion(row));
      return this.json(route, rows);
    }
    if (method === 'PATCH' && path === '/rest/v1/submissions') {
      return this.patchSubmission(route, url, request.postDataJSON());
    }
    if (method === 'POST' && path === '/rest/v1/rpc/save_submission_grade') {
      return this.saveGrade(route, request.postDataJSON());
    }
    if (method === 'POST' && path === '/rest/v1/rpc/save_submission_programs') {
      return this.savePrograms(route, request.postDataJSON());
    }
    if (method === 'POST' && path === '/rest/v1/rpc/save_program_grade') {
      return this.saveProgramGrade(route, request.postDataJSON());
    }
    if (method === 'GET' && path === '/rest/v1/question_sections') {
      const rows = [...this.sections].sort(
        (a, b) => a.position - b.position || a.name.localeCompare(b.name),
      );
      return this.json(route, rows);
    }
    if (method === 'POST' && path === '/rest/v1/question_sections') {
      const [section] = request.postDataJSON() as Array<Pick<SectionRow, 'name'>>;
      const row = this.addSection(section.name, 0);
      return this.json(route, this.wantsObject(request) ? row : [row], 201);
    }
    if (method === 'GET' && path === '/rest/v1/question_section_items') {
      return this.json(route, filterRows(this.sectionItems, url));
    }
    // Moving a question to another section or number (edit form).
    if (method === 'PATCH' && path === '/rest/v1/question_section_items') {
      const changes = request.postDataJSON() as Partial<SectionItemRow>;
      for (const row of filterRows(this.sectionItems, url)) Object.assign(row, changes);
      return this.json(route, null);
    }
    if (method === 'POST' && path === '/rest/v1/question_section_items') {
      const rows = request.postDataJSON() as SectionItemRow[];
      this.sectionItems.push(...rows);
      return this.json(route, null, 201);
    }
    return this.reject(route, `Unhandled Supabase request ${method} ${path}${url.search}`);
  }

  private filterSubmissions(url: URL): SubmissionRow[] {
    return filterRows([...this.submissions.values()], url);
  }

  // .single() asks for one object rather than an array.
  private wantsObject(request: Request): boolean {
    return (request.headers()['accept'] ?? '').includes('vnd.pgrst.object');
  }

  private withQuestion(row: SubmissionRow) {
    const question = this.questions.find((item) => item.id === row.question_id);
    return {
      ...row,
      submission_programs: this.programsOf(row.id).map(({ submission_id: _page, ...program }) => program),
      questions: question
        ? {
            id: question.id,
            question_name: question.question_name,
            question_type: question.question_type,
            model_answer: question.model_answer,
            test_cases: question.test_cases,
          }
        : null,
    };
  }

  private patchSubmission(route: Route, url: URL, changes: Partial<SubmissionRow>) {
    // Compare-and-set: the filters include grading_revision, so a stale
    // revision matches no row and the app sees null.
    const matched = this.filterSubmissions(url);
    for (const row of matched) {
      const questionChanged =
        'question_id' in changes && changes.question_id !== row.question_id;
      Object.assign(row, changes);
      row.grading_revision += 1;
      if (questionChanged) this.syncProgramOne(row);
    }
    return this.json(
      route,
      matched.map((row) => ({ grading_revision: row.grading_revision })),
    );
  }

  // Mirrors public.save_submission_grade: it writes only while the revision,
  // question and stored code all match, and returns the new revision or null.
  private saveGrade(route: Route, params: Record<string, any>) {
    const row = this.submissions.get(params['p_submission_id']);
    if (row) this.beforeGradeSave?.(row);

    const matches =
      !!row &&
      row.grading_revision === Number(params['p_grading_revision']) &&
      row.question_id === params['p_question_id'] &&
      row.verified_text === params['p_graded_code'] &&
      // Pages with programs are graded per program (20260926000900).
      this.programsOf(row.id).length === 0;
    if (!row || !matches) return this.json(route, null);

    const results = params['p_grading_results'] as Array<{ passed: boolean }>;
    const passed = results.filter((result) => result.passed).length;
    Object.assign(row, {
      grading_results: results,
      passed_test_cases: passed,
      total_test_cases: results.length,
      score_percent: results.length
        ? Number(((passed / results.length) * 100).toFixed(2))
        : null,
      graded_at: new Date().toISOString(),
      status: 'graded',
    });
    row.grading_revision += 1;
    return this.json(route, row.grading_revision);
  }

  // Mirrors public.save_submission_programs: guarded by the page's revision;
  // Program 1 is mirrored to the page row; programs are updated in place (a
  // changed one loses its grade); removed or emptied ones are deleted; the
  // page is graded only when every program is.
  private savePrograms(route: Route, params: Record<string, any>) {
    const page = this.submissions.get(params['p_submission_id']);
    if (!page || page.grading_revision !== Number(params['p_grading_revision'])) {
      return this.json(route, null);
    }
    const wanted = (params['p_programs'] as Array<{ verified_text: string; question_id?: string }>).map(
      (entry, index) => ({
        position: index + 1,
        question_id: (index === 0 ? entry.question_id || page.question_id : entry.question_id) ?? null,
        verified_text: entry.verified_text ?? '',
      }),
    );

    // The page row, as the submissions triggers treat it.
    const first = wanted[0];
    const inputsChanged =
      page.verified_text !== first.verified_text || page.question_id !== first.question_id;
    page.verified_text = first.verified_text;
    page.question_id = first.question_id;
    if (params['p_extracted_text'] !== null && params['p_extracted_text'] !== undefined) {
      page.extracted_text = params['p_extracted_text'];
    }
    if (inputsChanged) {
      page.grading_revision += 1;
      Object.assign(page, { grading_results: [], passed_test_cases: null, total_test_cases: null, score_percent: null, graded_at: null });
    }
    page.status = inputsChanged || page.status !== 'graded' ? 'verified' : page.status;

    const storable = (entry: (typeof wanted)[number]) =>
      entry.verified_text.trim() !== '' && !!entry.question_id;
    const kept = wanted.filter(storable);
    const existing = this.programsOf(page.id);
    // Program 1 by tab; Programs 2+ by question, else the row on their tab
    // that no other program took (20260926001100).
    const byQuestion = new Map<number, ProgramRow>();
    for (const entry of kept.filter((item) => item.position > 1)) {
      const row = existing.find(
        (program) =>
          program.position > 1 &&
          program.question_id === entry.question_id &&
          ![...byQuestion.values()].includes(program),
      );
      if (row) byQuestion.set(entry.position, row);
    }
    const taken = new Set(byQuestion.values());
    const plan = kept.map((entry) => {
      let row = byQuestion.get(entry.position);
      if (!row) {
        const onTab = existing.find((program) => program.position === entry.position);
        if (onTab && (entry.position === 1 || !taken.has(onTab))) row = onTab;
      }
      return { entry, row };
    });
    const planned = new Set(plan.map((item) => item.row).filter(Boolean));
    const replaceAll = params['p_replace_all'] !== false;
    let changed = 0;
    for (const program of existing) {
      if (planned.has(program)) continue;
      if (replaceAll || program.position <= wanted.length) {
        this.programs.splice(this.programs.indexOf(program), 1);
        changed += 1;
      }
    }
    for (const { entry, row } of plan) {
      if (!row) {
        this.addProgram(page.id, entry.position, entry.question_id!, entry.verified_text);
        changed += 1;
        continue;
      }
      const inputsDiffer =
        row.verified_text !== entry.verified_text || row.question_id !== entry.question_id;
      if (inputsDiffer || row.position !== entry.position) changed += 1;
      row.position = entry.position;
      if (inputsDiffer) {
        Object.assign(row, {
          question_id: entry.question_id,
          verified_text: entry.verified_text,
          grading_results: [],
          passed_test_cases: null,
          total_test_cases: null,
          score_percent: null,
          graded_at: null,
          grading_revision: row.grading_revision + 1,
        });
      }
    }
    // Any program change moves the page revision (20260926000700).
    if (changed > 0) page.grading_revision += 1;
    this.syncPageStatus(page);
    return this.json(route, page.grading_revision);
  }

  // Mirrors public.sync_program_one_with_page: Program 1 follows the page's
  // question (moved and ungraded, created from saved code, or removed).
  private syncProgramOne(page: SubmissionRow) {
    const programOne = this.programsOf(page.id).find((program) => program.position === 1);
    if (!page.question_id) {
      if (programOne) this.programs.splice(this.programs.indexOf(programOne), 1);
    } else if (programOne) {
      if (programOne.question_id !== page.question_id) {
        Object.assign(programOne, {
          question_id: page.question_id,
          grading_results: [],
          passed_test_cases: null,
          total_test_cases: null,
          score_percent: null,
          graded_at: null,
          grading_revision: programOne.grading_revision + 1,
        });
      }
    } else if (page.verified_text?.trim()) {
      this.addProgram(page.id, 1, page.question_id, page.verified_text);
    }
    this.syncPageStatus(page);
  }

  // Mirrors public.save_program_grade.
  private saveProgramGrade(route: Route, params: Record<string, any>) {
    const program = this.programs.find((item) => item.id === params['p_program_id']);
    if (program) this.beforeProgramGradeSave?.(program);
    const matches =
      !!program &&
      program.grading_revision === Number(params['p_grading_revision']) &&
      program.question_id === params['p_question_id'] &&
      program.verified_text === params['p_graded_code'];
    if (!program || !matches) return this.json(route, null);

    const results = params['p_grading_results'] as Array<{ passed: boolean }>;
    const passed = results.filter((result) => result.passed).length;
    Object.assign(program, {
      grading_results: results,
      passed_test_cases: passed,
      total_test_cases: results.length,
      score_percent: results.length ? Number(((passed / results.length) * 100).toFixed(2)) : null,
      graded_at: new Date().toISOString(),
      grading_revision: program.grading_revision + 1,
    });
    this.syncPageStatus(this.submissions.get(program.submission_id)!);
    return this.json(route, program.grading_revision);
  }

  private syncPageStatus(page: SubmissionRow) {
    if (page.status !== 'verified' && page.status !== 'graded') return;
    const programs = this.programsOf(page.id);
    page.status = programs.length && programs.every((program) => program.graded_at) ? 'graded' : 'verified';
  }

  // ── Judge0 wrapper ───────────────────────────────────────

  private async handleJudge0(route: Route) {
    const request = route.request();
    const url = new URL(request.url());
    this.record(request, url);

    if (request.method() === 'OPTIONS') {
      return route.fulfill({ status: 204, headers: cors() });
    }
    if (this.judge0FailureStatus !== null) {
      return this.json(route, { detail: 'Judge0 unavailable' }, this.judge0FailureStatus);
    }

    const body = request.postDataJSON();
    if (url.pathname.endsWith('/run')) {
      return this.json(route, this.judge0(body));
    }
    if (url.pathname.endsWith('/run-batch')) {
      return this.json(
        route,
        (body.runs as Judge0Run[]).map((run) => this.judge0(run)),
      );
    }
    return this.reject(route, `Unhandled Judge0 request ${url.pathname}`);
  }

  // ── helpers ──────────────────────────────────────────────

  private record(request: Request, url: URL) {
    if (request.method() === 'OPTIONS') return;
    let body: any = null;
    try {
      body = request.postDataJSON();
    } catch {
      body = request.postData();
    }
    this.requests.push({ method: request.method(), url, body });
  }

  private json(route: Route, body: unknown, status = 200) {
    return route.fulfill({
      status,
      headers: { ...cors(), 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  private reject(route: Route, message: string) {
    this.unexpected.push(message);
    return route.fulfill({
      status: 501,
      headers: { ...cors(), 'content-type': 'application/json' },
      body: JSON.stringify({ message }),
    });
  }
}

// Applies the PostgREST `column=eq.value` filters the app uses.
function filterRows<T extends object>(rows: T[], url: URL): T[] {
  const filters = [...url.searchParams.entries()].filter(([, value]) =>
    value.startsWith('eq.'),
  );
  return rows.filter((row) =>
    filters.every(
      ([column, value]) => String(row[column as keyof T]) === value.slice(3),
    ),
  );
}

function cors() {
  return {
    'access-control-allow-origin': '*',
    'access-control-allow-headers': '*',
    'access-control-allow-methods': 'GET,POST,PATCH,OPTIONS',
  };
}

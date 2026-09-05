export type AssessmentStatus = 'draft' | 'active' | 'closed';

export type SupabaseRelation<T> = T | T[] | null;

export interface Assessment {
  id: string;
  name: string;
  status: AssessmentStatus;
  starts_at: string | null;
}

export interface BlockSection {
  id: string;
  name: string;
}

export interface Student {
  id: string;
  student_number: string;
  display_name: string;
}

export interface TestCase {
  test_code: string;
  test_input: string;
  expected_output: string;
  mark: number;
  is_hidden?: boolean;
}

export interface SubmissionQuestion {
  id: string;
  question_name: string;
  question_type: 'function' | 'program';
  model_answer: string;
  test_cases: TestCase[];
}

export interface AssessmentQuestion {
  assessment_id: string;
  question_id: string;
  starter_code: string;
  position: number;
  questions: SupabaseRelation<SubmissionQuestion>;
}

export interface AssessmentRosterEntry {
  assessment_id: string;
  student_id: string;
  block_section_id: string;
  students: SupabaseRelation<Student>;
  block_sections: SupabaseRelation<BlockSection>;
}

export interface SubmissionAssessmentContext {
  assessments: SupabaseRelation<Assessment>;
}

export interface SubmissionRosterContext {
  students: SupabaseRelation<Student>;
  block_sections: SupabaseRelation<BlockSection>;
}

export interface Submission {
  id: string;
  image_url: string;
  student_name?: string;
  captured_at: string;
  status?: string;
  extracted_text?: string;
  verified_text?: string;
  topic?: string;
  question_id?: string;
  assessment_id?: string;
  student_id?: string;
  block_section_id?: string;
  verified_version: number;
  is_current: boolean;
  questions?: SupabaseRelation<SubmissionQuestion>;
  assessment_questions?: SupabaseRelation<SubmissionAssessmentContext>;
  assessment_roster?: SupabaseRelation<SubmissionRosterContext>;
}

export interface SubmissionContextOptions {
  assessments: Assessment[];
  assessmentQuestions: AssessmentQuestion[];
  roster: AssessmentRosterEntry[];
}

export interface SubmissionDetailsUpdate {
  topic: string;
  assessment_id: string;
  question_id: string;
  student_id: string;
  block_section_id: string;
}

SET session_replication_role = replica;

--
-- PostgreSQL database dump
--

-- \restrict Xd6ZazMUDjwE6jj3FKA58Pgcmfl7wqCVi5R47zHLFVoyA1v73osH0aQhOJLbmCJ

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: questions; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."questions" ("id", "question_name", "question_text", "model_answer", "test_cases", "created_at", "validation_status", "can_publish", "model_validation_results") VALUES
	('954a8f00-8c73-4367-ad11-4557ee28ce7e', 'Programming 1A', 'Write a function that adds two integers and returns the result.', 'int add(int a, int b){
  return a + b;
}', '[{"mark": 2, "test_code": "Test Code: printf(\"%d\", add(2, 3));", "expected_output": "5"}]', '2026-07-16 13:05:24.468872+00', 'draft', false, '[]'),
	('1b0dbba3-b2bf-4150-9654-9808d7d96f3b', 'Even and odd', 'Even and odd', '#include <stdio.h>

int main(){
 printf("Hello world");
}', '[{"mark": 2, "test_code": " printf(\"Hello world\") ", "expected_output": "Hello world"}]', '2026-07-18 05:38:55.44301+00', 'draft', false, '[]'),
	('862c0506-d68d-460b-b96c-d5f9a6f63763', 'anem', 'name', '#include <stdio.h>

int main(){
 printf("jayrald"); 
}', '[{"mark": 2, "test_code": "printf(\"jayrald\"); ", "expected_output": "jayrald"}]', '2026-07-18 05:57:00.470042+00', 'draft', false, '[]'),
	('3881feae-06fb-43fd-9c7a-caf91e58faa9', 'Programming A1', 'write a c program that prints "hello world" to the screen', '#include <stdio.h>

int main(void) {
    printf("Hello World");
    return 0;
}', '[{"mark": 2, "test_code": "#include <stdio.h>\n\nint main(void) {\nprintf(\"hello world\");\nreturn 0;\n\n}", "expected_output": "hello world"}]', '2026-07-19 21:02:33.631766+00', 'draft', false, '[]'),
	('11ad97c2-2aa4-4b90-8a8d-d4c784e1f97d', 'Well Order', 'Create a function ', 'int isWellOrdered(int n) {
    int prev = 10;

    while (n > 0) {
        int digit = n % 10;

        if (digit > prev) {
            return 0;
        }

        prev = digit;
        n /= 10;
    }

    return 1;
}', '[{"mark": 2, "is_hidden": true, "test_code": "int main() {\n    if (isWellOrdered(123))\n        printf(\"Well ordered\");\n    else\n        printf(\"Not well ordered\");\n\n    return 0;\n}", "expected_output": "Well ordered"}, {"mark": 2, "is_hidden": true, "test_code": "int main() {\n    if (isWellOrdered(132))\n        printf(\"Well ordered\");\n    else\n        printf(\"Not well ordered\");\n\n    return 0;\n}", "expected_output": "Not well ordered"}]', '2026-07-20 04:30:44.683117+00', 'validated', true, '[{"index": 0, "label": "Hidden Test 1", "passed": true, "status": "Passed", "isHidden": true, "diagnostics": "", "actualOutput": "", "expectedOutput": ""}, {"index": 1, "label": "Hidden Test 2", "passed": true, "status": "Passed", "isHidden": true, "diagnostics": "", "actualOutput": "", "expectedOutput": ""}]'),
	('e1265442-6a60-471e-9730-6ab26128083d', 'Sum of two numbers', 'write a function that accepts 2 integers and display the sum of 2 numbers', 'void sumof2(int x, int y){
  int sum = x+y;
  
  printf("the sum of %d and %d is = %d ", x, y, sum);
  
}', '[{"mark": 2, "test_code": "int main(){\n int x = 2, y = 1;\nsumof2(x,y);\n}", "expected_output": "3"}]', '2026-07-20 06:20:18.698358+00', 'draft', false, '[{"index": 0, "label": "Test Case 1", "passed": false, "status": "Accepted", "isHidden": false, "diagnostics": "", "actualOutput": "the sum of 2 and 1 is = 3 ", "expectedOutput": "3"}]'),
	('2cc5a71f-b95b-4d66-9d3e-324474c1d368', 'Count Even Numbers in an Array', 'Write a C function named countEven that accepts an integer array and its size. The function should return the number of even numbers in the array.', 'int countEven(int arr[], int size) {
    int count = 0;

    for (int i = 0; i < size; i++) {
        if (arr[i] % 2 == 0) {
            count++;
        }
    }

    return count;
}', '[{"mark": 2, "test_code": "int main(void){\nint arr[] = {1, 2, 3, 4, 5, 6};\nint size = 6;\n\nprintf(\"%d\", countEven(arr, size));\n}", "expected_output": "3"}]', '2026-07-20 04:49:17.697684+00', 'draft', false, '[{"index": 0, "label": "Test Case 1", "passed": true, "status": "Accepted", "isHidden": false, "diagnostics": "", "actualOutput": "3", "expectedOutput": "3"}, {"index": 1, "label": "Test Case 2", "passed": false, "status": "Compilation Error", "isHidden": false, "diagnostics": "main.c: In function ‘main’:\nmain.c:21:1: error: expected declaration or statement at end of input\n   21 | int size = 5;\n      | ^~~\n", "actualOutput": "", "expectedOutput": "Odd"}]'),
	('05ce850e-7d37-4a66-93b2-3943afa2b31d', 'Programming 1B', 'Write a function that adds two integers and returns the result.', 'int add(int a, int b){
  return a + b;
}', '[{"mark": 2, "test_code": "printf(\"%d\", add(2, 3));", "expected_output": "5"}]', '2026-07-16 13:15:57.13156+00', 'draft', false, '[]');


--
-- Data for Name: submissions; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."submissions" ("id", "image_url", "student_name", "captured_at", "status", "extracted_text", "verified_at", "verified_text") VALUES
	('37603695-4e98-4458-b163-ecbefe1da420', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1784208666867.jpg', NULL, '2026-07-16 13:31:10.790395+00', 'pending', NULL, NULL, NULL),
	('5424c20b-f825-4f36-a5b6-c6712c1f78be', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1784208845492.jpg', NULL, '2026-07-16 13:34:09.040261+00', 'pending', NULL, NULL, NULL),
	('7b2f4eac-fe91-43f4-8e1f-16395424cd56', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1784211182593.jpg', NULL, '2026-07-16 14:13:07.077567+00', 'pending', NULL, NULL, NULL),
	('efcff566-14b1-4053-91c9-8f506c9a9aef', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1784209910839.jpg', NULL, '2026-07-16 13:51:54.087455+00', 'pending', NULL, NULL, NULL),
	('cd275d93-bd0a-417b-a34b-135aeaae076e', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1784228050709.jpg', NULL, '2026-07-16 18:54:15.404476+00', 'verified', NULL, NULL, NULL),
	('b0d0e724-44c1-4d04-8d6f-d41117c75da8', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1784525927943.jpg', NULL, '2026-07-20 05:39:01.268552+00', 'pending', NULL, NULL, NULL),
	('da252aa9-c6b8-4e1d-8a52-9ee091662b3c', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1784203489214.jpg', NULL, '2026-07-16 12:04:51.687995+00', 'verified', 'Include
<stdio.n7
main (void) E
Int
printf ("Hello worL"):
return O;
3', '2026-07-24 04:04:06.81+00', '#include <stdio.h>

int main (void) {

printf ("Hello World");

return O;

}');

UPDATE "public"."submissions"
SET "verified_version" = 1
WHERE "verified_text" IS NOT NULL;


--
-- PostgreSQL database dump complete
--

-- \unrestrict Xd6ZazMUDjwE6jj3FKA58Pgcmfl7wqCVi5R47zHLFVoyA1v73osH0aQhOJLbmCJ

RESET ALL;

-- Stable local cohort for assessment and cross-section similarity development.
INSERT INTO public.assessments (id, name, status, starts_at)
VALUES (
  'a0000000-0000-0000-0000-000000000001',
  'Programming Fundamentals Midterm',
  'active',
  '2026-09-05 01:00:00+00'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.block_sections (id, name)
VALUES
  ('b0000000-0000-0000-0000-000000000001', 'BSCS 2A'),
  ('b0000000-0000-0000-0000-000000000002', 'BSCS 2B')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.students (id, student_number, display_name)
VALUES
  ('c0000000-0000-0000-0000-000000000001', '2026-0001', 'Alex Santos'),
  ('c0000000-0000-0000-0000-000000000002', '2026-0002', 'Bea Cruz'),
  ('c0000000-0000-0000-0000-000000000003', '2026-0003', 'Carlo Reyes')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.assessment_questions (
  assessment_id,
  question_id,
  starter_code,
  position
)
VALUES (
  'a0000000-0000-0000-0000-000000000001',
  '954a8f00-8c73-4367-ad11-4557ee28ce7e',
  E'int add(int a, int b) {\n  /* Write your solution. */\n}',
  1
)
ON CONFLICT (assessment_id, question_id) DO NOTHING;

INSERT INTO public.assessment_roster (
  assessment_id,
  student_id,
  block_section_id
)
VALUES
  (
    'a0000000-0000-0000-0000-000000000001',
    'c0000000-0000-0000-0000-000000000001',
    'b0000000-0000-0000-0000-000000000001'
  ),
  (
    'a0000000-0000-0000-0000-000000000001',
    'c0000000-0000-0000-0000-000000000002',
    'b0000000-0000-0000-0000-000000000002'
  ),
  (
    'a0000000-0000-0000-0000-000000000001',
    'c0000000-0000-0000-0000-000000000003',
    'b0000000-0000-0000-0000-000000000001'
  )
ON CONFLICT (assessment_id, student_id) DO NOTHING;

INSERT INTO public.submissions (
  id,
  image_url,
  student_name,
  status,
  verified_at,
  verified_text,
  topic,
  assessment_id,
  question_id,
  student_id,
  block_section_id
)
VALUES
  (
    'd0000000-0000-0000-0000-000000000001',
    'https://example.test/similarity/alex.png',
    'Alex Santos',
    'verified',
    now(),
    'int add(int a, int b) { int total = a + b; return total; }',
    'Functions',
    'a0000000-0000-0000-0000-000000000001',
    '954a8f00-8c73-4367-ad11-4557ee28ce7e',
    'c0000000-0000-0000-0000-000000000001',
    'b0000000-0000-0000-0000-000000000001'
  ),
  (
    'd0000000-0000-0000-0000-000000000002',
    'https://example.test/similarity/bea.png',
    'Bea Cruz',
    'verified',
    now(),
    'int add(int x, int y) { int sum = x + y; return sum; }',
    'Functions',
    'a0000000-0000-0000-0000-000000000001',
    '954a8f00-8c73-4367-ad11-4557ee28ce7e',
    'c0000000-0000-0000-0000-000000000002',
    'b0000000-0000-0000-0000-000000000002'
  ),
  (
    'd0000000-0000-0000-0000-000000000003',
    'https://example.test/similarity/carlo.png',
    'Carlo Reyes',
    'verified',
    now(),
    'int add(int a, int b) { while (b != 0) { a++; b--; } return a; }',
    'Functions',
    'a0000000-0000-0000-0000-000000000001',
    '954a8f00-8c73-4367-ad11-4557ee28ce7e',
    'c0000000-0000-0000-0000-000000000003',
    'b0000000-0000-0000-0000-000000000001'
  )
ON CONFLICT (id) DO NOTHING;

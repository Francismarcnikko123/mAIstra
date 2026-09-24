SET session_replication_role = replica;

--
-- PostgreSQL database dump
--

-- \restrict leP5hE9SJ3OKbpCl5ugWsGagGoFG95HjD2hfbwrJQfIcyTNQ8gpzu2kxSvD4BGI

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

INSERT INTO "public"."questions" ("id", "question_name", "question_text", "model_answer", "test_cases", "created_at", "validation_status", "can_publish", "model_validation_results", "question_type") VALUES
	('eb9df3fc-e1c3-4d30-a13d-6333dd7d5eec', 'the sum of two numbers', 'add the two numbers', '#include <stdio.h>

int main()
{
    int num1 = 5, num2 = 10, total;
    
    num1 = num1+num2;
    printf("sum: %d", num1);

    return 0;
}', '[{"mark": 2, "test_code": "", "test_input": "", "expected_output": "sum: 15"}]', '2026-08-06 16:00:28.218158+00', 'draft', false, '[]', 'program'),
	('ab31a894-a044-403c-8fd1-6b93c771d162', 'write a program that adds the two numbers', 'asd', '#include <stdio.h>
int main () {
int a, b, sum;
scanf ("%d %d ", &a ,&b);
sum = a + b;
printf ("sum: %d\n ", sum);
return 0;
}', '[{"mark": 2, "test_code": "", "test_input": "5 3", "expected_output": "sum: 8"}]', '2026-08-06 16:14:11.450585+00', 'draft', false, '[]', 'program');


--
-- Data for Name: submissions; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."submissions" ("id", "image_url", "student_name", "captured_at", "status", "extracted_text", "verified_at", "verified_text", "topic", "question_id") VALUES
	('816a9fce-e838-4d8d-a993-2afd11a269c7', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785906683554.jpg', NULL, '2026-08-05 05:11:35.655933+00', 'verified', '#include <stdio.h>
int main () {
int arr [5] = {1,2,3,4,5};
for (int i = 0; i < 5 ; i++) {
printf ("%d\n", arr [i]);
}
return 0;
}', '2026-08-06 16:29:02.794+00', '#include <stdio.h>
int main () {
int arr [5] = {1,2,3,4,5};
for (int i = 0; i < 5 ; i++) {
printf ("%d\n", arr [i]);
}
return 0;
}', 'Uncategorized', NULL),
	('7966fcdb-f33b-44fb-87f3-f1edc1b147bd', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786006326756.jpg', NULL, '2026-08-06 08:52:08.392457+00', 'verified', 'if (x>5);{
printf("Hello(n");
if (score = 100) {
printf ("perfect!\n");
}
do
×t+i
while(x<5)', '2026-08-06 10:03:35.045+00', 'if (x > 5); {
    printf("Hello\n");
}

if (score = 100) {
    printf("Perfect!\n");
}

do {
    x++;
} while (x < 5)', 'Uncategorized', NULL),
	('85cb8a9d-cc15-4aa5-a977-ac4f733eedca', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785907170842.jpg', NULL, '2026-08-05 05:19:54.33639+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('2b8a28d8-9383-4d0f-b3c5-d6d9193dbce9', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785907663332.jpg', NULL, '2026-08-05 05:27:45.659886+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('d68a3a7a-526e-4250-9e42-1311337689f3', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785907816105.jpg', NULL, '2026-08-05 05:30:16.751461+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('36152478-95db-43ab-b970-71413394446d', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785907946017.jpg', NULL, '2026-08-05 05:32:34.422585+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('2a10d909-3e22-4cec-afc1-023e01edc77d', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785907714374.jpg', NULL, '2026-08-05 05:28:36.513833+00', 'verified', '#include <stdio.h>
int main() {
    int arr[5] = {1,2,3,4,5};
    for (int i = 0; i < 5; i++) {
        printf("%d\n", arr[i]);
    }
    return 0;
}   ', '2026-08-06 15:22:28.111+00', '#include <stdio.h>
int main() {
    int arr[5] = {1,2,3,4,5};
    for (int i = 0; i < 5; i++) {
        printf("%d\n", arr[i]);
    }
    return 0;
}', 'Uncategorized', NULL),
	('00a005cc-ba42-4ac3-a15e-bfa0356ca3ea', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785907079465.jpg', NULL, '2026-08-05 05:18:04.449378+00', 'verified', '#include <stdio.h>
int add (int x, int y) {
return x + y;
}
int main () {
int result = add (3,4);
printf ("Result: %d\n", result);
return 0;
}', '2026-08-06 16:16:23.568+00', '#include <stdio.h>
int add (int x, int y) {
return x + y;
}
int main () {
int result = add (3,4);
printf ("Result: %d\n", result);
return 0;
}', 'Uncategorized', NULL),
	('129d45fe-e405-4d9c-afcb-2a7cd828697b', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785999800324.jpg', NULL, '2026-08-06 07:05:25.173292+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('885d5dda-6af5-4b7c-99ad-186c77e8689a', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786004210424.jpg', NULL, '2026-08-06 08:16:55.35412+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('f6b55df2-7840-4ee3-a1d9-96ba7cac5fcf', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786004546751.jpg', NULL, '2026-08-06 08:22:31.039866+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('d427d75c-dd8e-45a5-9eb2-472b8c0a7b97', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786004751964.jpg', NULL, '2026-08-06 08:25:56.274202+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('fb214db5-c6cd-455f-ab4a-cc184e89938a', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786005057612.jpg', NULL, '2026-08-06 08:31:01.916068+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('84517bcd-385a-4d61-942d-24fc16dbc56f', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786005116616.jpg', NULL, '2026-08-06 08:31:58.643937+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('fc951bc0-686b-4f1f-9ad5-dc66b16aadb4', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786005188365.jpg', NULL, '2026-08-06 08:33:10.611842+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('c893cd52-abbf-446b-85c5-bb9f92c0da0d', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786006122447.jpg', NULL, '2026-08-06 08:48:47.803886+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('9b826cbf-b268-4af7-8a94-5a9a7c0bb22f', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786006237786.jpg', NULL, '2026-08-06 08:50:42.15815+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('4fe49edf-be76-4509-b871-4435a25ac978', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786008147023.jpg', NULL, '2026-08-06 09:22:29.399934+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('4b45b90a-fa93-4e32-a0e3-e2a8c3756498', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786008437037.jpg', NULL, '2026-08-06 09:27:24.37793+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('fcf6f883-cd09-4490-b319-56106fb4b9d3', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786008513457.jpg', NULL, '2026-08-06 09:28:35.848707+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('9a53f91f-67b9-472e-af6d-ed8e6ff6cf66', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786008560297.jpg', NULL, '2026-08-06 09:29:22.211992+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('826cc0e5-9f09-4246-a8a0-914e4b730a5d', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785907249357.jpg', NULL, '2026-08-05 05:20:53.239424+00', 'verified', '#include <stdio.h>
int main() {
    int num = 10;
    int *ptr = &num;
    printf("Value: %d\n", *ptr);
    return 0;
}', '2026-08-09 19:36:16.908+00', '#include <stdio.h>
int main() {
    int num = 10;
    int *ptr = &num;
    printf("Value: %d\n", *ptr);
    return 0;
}', 'Uncategorized', NULL),
	('b6986e8d-c1c0-4a47-bc10-0267485c62d0', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786006376941.jpg', NULL, '2026-08-06 08:52:58.680727+00', 'verified', 'Include stdio. n>
int main a{
int rows= 4;
int cols = 5;
for (int i= 1; i<= rows; i++){
for (int j = 1 ; j<= colsi jt+ ){
printf ("* ");
3
print f ("In ");
j
return 0;', '2026-08-06 10:04:30.678+00', '#include <stdio.h>
int main() {
    int rows = 4;
    int cols = 5;
    for (int i = 1; i <= rows; i++) {
        for (int j = 1; j <= cols; j++) {
            printf("* ");
        }
        printf("\n");
    }
    return 0;
}', 'Uncategorized', NULL),
	('94300ec8-3700-498f-8215-a6c8c774d33f', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785902823075.jpg', NULL, '2026-08-05 04:07:30.534744+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('b78b49f9-d052-4160-8508-0c91fadb9b5f', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1785907001911.jpg', NULL, '2026-08-05 05:16:48.499206+00', 'verified', '#include <stdio.h>
int main () {
int a, b, sum;
scanf (" %d %d ", &a ,&b);
sum = a + b;
printf ("sum = %d\n ", sum);
return 0;
}', '2026-08-07 03:13:34.982+00', '#include <stdio.h>
int main () {
int a, b, sum;
scanf (" %d %d ", &a ,&b);
sum = a + b;
printf ("sum = %d\n ", sum);
return 0;
}', 'Uncategorized', NULL),
	('52ba5f3f-90f0-4b86-be93-4b6a9840855e', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786006487702.jpg', NULL, '2026-08-06 08:54:51.860001+00', 'verified', '#include <stdio.h>
int mainc) printf ("printing even numbers from 1 to 10 (stopping if we hit 8) : \n");
for (int i= 1;i <=10; 1++){
if (i% 2! = 0) {
continue;
7
if Ci==8){ printf (" Reached 8! Breaking out of loop. Sn");
breaki
b
prints ("Number: %d\n", i );
l
return 0;', '2026-08-06 10:05:53.479+00', '#include <stdio.h>
int main() {
    printf("Printing even numbers from 1 to 10 (stopping if we hit 8):\n");
    for (int i = 1; i <= 10; i++) {
        if (i % 2 != 0) {
            continue;
        }
        if (i == 8) {
            printf("Reached 8! Breaking out of loop.\n");
            break;
        }
        printf("Number: %d\n", i);
    }
    return 0;
}', 'Uncategorized', NULL),
	('e4005645-6d3b-4a84-a19b-b5c8dd72ad1c', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786011168605.jpg', NULL, '2026-08-06 10:12:53.270214+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL),
	('785d998e-caf7-4eb6-a95d-97648390f0a5', 'https://cvtshfshqccuncamvnkl.supabase.co/storage/v1/object/public/handwritten-submissions/submission_1786011318345.jpg', NULL, '2026-08-06 10:15:20.285036+00', 'pending', NULL, NULL, NULL, 'Uncategorized', NULL);


--
-- PostgreSQL database dump complete
--

-- \unrestrict leP5hE9SJ3OKbpCl5ugWsGagGoFG95HjD2hfbwrJQfIcyTNQ8gpzu2kxSvD4BGI

RESET ALL;

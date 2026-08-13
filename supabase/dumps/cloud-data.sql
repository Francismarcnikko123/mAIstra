SET session_replication_role = replica;

--
-- PostgreSQL database dump
--

-- \restrict 9iZZ1qmESdmtacRfXxaUUZitfnNj2GEucDVGrEn8FaHba7i4JQaWpb5KqL1wWNo

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
-- Data for Name: audit_log_entries; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: custom_oauth_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: flow_state; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: identities; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: instances; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: oauth_clients; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: sessions; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: mfa_amr_claims; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: mfa_factors; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: mfa_challenges; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: oauth_authorizations; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: oauth_client_states; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: oauth_consents; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: one_time_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: sso_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: saml_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: saml_relay_states; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: sso_domains; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: webauthn_challenges; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: webauthn_credentials; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



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
-- Data for Name: buckets; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

INSERT INTO "storage"."buckets" ("id", "name", "owner", "created_at", "updated_at", "public", "avif_autodetection", "file_size_limit", "allowed_mime_types", "owner_id", "type") VALUES
	('handwritten-submissions', 'handwritten-submissions', NULL, '2026-07-16 10:33:24.471625+00', '2026-07-16 10:33:24.471625+00', true, false, NULL, NULL, NULL, 'STANDARD');


--
-- Data for Name: buckets_analytics; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: buckets_vectors; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: objects; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

INSERT INTO "storage"."objects" ("id", "bucket_id", "name", "owner", "created_at", "updated_at", "last_accessed_at", "metadata", "version", "owner_id", "user_metadata") VALUES
	('621508f3-bfed-49e2-960b-42a88b9c354b', 'handwritten-submissions', 'submission_1785907170842.jpg', NULL, '2026-08-05 05:19:54.070348+00', '2026-08-05 05:19:54.070348+00', '2026-08-05 05:19:54.070348+00', '{"eTag": "\"91e905744908f5f563d307a5452ecff8\"", "size": 853218, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:19:55.000Z", "contentLength": 853218, "httpStatusCode": 200}', '7408bd41-d8fa-4af9-8651-0f61997178b3', NULL, '{}'),
	('981c7053-2f19-412b-989b-ce8a0fd92d56', 'handwritten-submissions', 'submission_1785907249357.jpg', NULL, '2026-08-05 05:20:53.036816+00', '2026-08-05 05:20:53.036816+00', '2026-08-05 05:20:53.036816+00', '{"eTag": "\"5555551d7acddd364dfb6f39e9290cf3\"", "size": 995383, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:20:53.000Z", "contentLength": 995383, "httpStatusCode": 200}', '2a30d258-100d-4e52-a4cf-7177e69859e5', NULL, '{}'),
	('9804178d-e053-4c4c-80ba-a9a17ea49df3', 'handwritten-submissions', 'submission_1785907816105.jpg', NULL, '2026-08-05 05:30:16.558511+00', '2026-08-05 05:30:16.558511+00', '2026-08-05 05:30:16.558511+00', '{"eTag": "\"8026f29538555f63ad4a10e3e3ed9521\"", "size": 886167, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:30:17.000Z", "contentLength": 886167, "httpStatusCode": 200}', '2edfe725-05aa-4ccb-a62d-c3cf81a69ca6', NULL, '{}'),
	('eb209091-e755-4621-94f6-8dd879dcb927', 'handwritten-submissions', 'submission_1786004210424.jpg', NULL, '2026-08-06 08:16:54.733906+00', '2026-08-06 08:16:54.733906+00', '2026-08-06 08:16:54.733906+00', '{"eTag": "\"a10cc79d1cf7874b378c4228ea2e6759\"", "size": 247892, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:16:55.000Z", "contentLength": 247892, "httpStatusCode": 200}', 'c3396f87-cc66-408a-adde-0d8051a5d04d', NULL, '{}'),
	('0ce2c6fd-91d1-41c8-b5ad-f491e8331310', 'handwritten-submissions', 'submission_1786004546751.jpg', NULL, '2026-08-06 08:22:30.355324+00', '2026-08-06 08:22:30.355324+00', '2026-08-06 08:22:30.355324+00', '{"eTag": "\"27d360cfe86f0608f253b3ec8cc9746b\"", "size": 243314, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:22:31.000Z", "contentLength": 243314, "httpStatusCode": 200}', '5969d9db-1311-46d0-9cfd-013403ec8f6a', NULL, '{}'),
	('7cb06d6d-53b3-4263-a57d-3308f706a7c6', 'handwritten-submissions', 'submission_1786004751964.jpg', NULL, '2026-08-06 08:25:55.865592+00', '2026-08-06 08:25:55.865592+00', '2026-08-06 08:25:55.865592+00', '{"eTag": "\"ea163c4de3fcb2c4100c6a683e5096ce\"", "size": 352221, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:25:56.000Z", "contentLength": 352221, "httpStatusCode": 200}', 'a20ac22e-fb49-47e2-8fb3-120e26a22ada', NULL, '{}'),
	('ee35433b-0c5e-49c7-a746-cc734dbf872a', 'handwritten-submissions', 'submission_1786006122447.jpg', NULL, '2026-08-06 08:48:47.316406+00', '2026-08-06 08:48:47.316406+00', '2026-08-06 08:48:47.316406+00', '{"eTag": "\"30afef5c52dd37f0bd51de7d1a522d6e\"", "size": 945019, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:48:48.000Z", "contentLength": 945019, "httpStatusCode": 200}', '70668edd-8e8b-4370-b36a-3ce10bf0484e', NULL, '{}'),
	('3f4e9268-723b-47d7-a401-981ddf0e527e', 'handwritten-submissions', 'submission_1786006237786.jpg', NULL, '2026-08-06 08:50:41.921905+00', '2026-08-06 08:50:41.921905+00', '2026-08-06 08:50:41.921905+00', '{"eTag": "\"a99508b80a747cc8a6745b49f3123d3f\"", "size": 354440, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:50:42.000Z", "contentLength": 354440, "httpStatusCode": 200}', '33a09ded-acef-4f66-b053-afc4a2761759', NULL, '{}'),
	('0c11aa3c-6537-432d-8a8d-00b8f8532feb', 'handwritten-submissions', 'submission_1786006326756.jpg', NULL, '2026-08-06 08:52:08.103235+00', '2026-08-06 08:52:08.103235+00', '2026-08-06 08:52:08.103235+00', '{"eTag": "\"0f9880fc78540bf8fb0e4f5bed2c35e7\"", "size": 348530, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:52:09.000Z", "contentLength": 348530, "httpStatusCode": 200}', 'ac36911d-ba88-496d-acdf-72afaac82476', NULL, '{}'),
	('bbb5a427-38b6-40e4-8b81-d9841ee30fc7', 'handwritten-submissions', 'submission_1786006376941.jpg', NULL, '2026-08-06 08:52:58.453961+00', '2026-08-06 08:52:58.453961+00', '2026-08-06 08:52:58.453961+00', '{"eTag": "\"84f035aac505365681ea42ebbf81c032\"", "size": 294572, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:52:59.000Z", "contentLength": 294572, "httpStatusCode": 200}', 'f3eb7420-3019-4c34-99aa-d3b48bbb2163', NULL, '{}'),
	('547ee85d-c0f5-4444-8d26-a46f9886731e', 'handwritten-submissions', 'submission_1786006487702.jpg', NULL, '2026-08-06 08:54:51.292292+00', '2026-08-06 08:54:51.292292+00', '2026-08-06 08:54:51.292292+00', '{"eTag": "\"15c0109f16d94e0fdee41ff6f76f8369\"", "size": 350010, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:54:52.000Z", "contentLength": 350010, "httpStatusCode": 200}', 'c6d548a9-6977-48ba-bbce-29f3c942a111', NULL, '{}'),
	('0cbbc576-3d4b-4643-9367-c0ad6c9af46f', 'handwritten-submissions', 'submission_1785907663332.jpg', NULL, '2026-08-05 05:27:45.072421+00', '2026-08-05 05:27:45.072421+00', '2026-08-05 05:27:45.072421+00', '{"eTag": "\"ca7a73f222cc008016b7fea0f847b1a7\"", "size": 1130679, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:27:46.000Z", "contentLength": 1130679, "httpStatusCode": 200}', '6ee46ede-93b3-4589-aaad-f05e38ff00aa', NULL, '{}'),
	('7d46a1c1-d946-4519-adc3-626212bbcd5c', 'handwritten-submissions', 'submission_1785907714374.jpg', NULL, '2026-08-05 05:28:36.272523+00', '2026-08-05 05:28:36.272523+00', '2026-08-05 05:28:36.272523+00', '{"eTag": "\"bd20205830b08fd12f8308b69f2218be\"", "size": 1013977, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:28:37.000Z", "contentLength": 1013977, "httpStatusCode": 200}', '36cca332-9657-4232-8532-86446d853bc7', NULL, '{}'),
	('78af9e1d-0ee4-47ea-ac9c-220ef3f457f8', 'handwritten-submissions', 'submission_1785907946017.jpg', NULL, '2026-08-05 05:32:34.083241+00', '2026-08-05 05:32:34.083241+00', '2026-08-05 05:32:34.083241+00', '{"eTag": "\"3bf48a4df0d0a627d6985ec8041541af\"", "size": 1022652, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:32:35.000Z", "contentLength": 1022652, "httpStatusCode": 200}', 'a6df8ba1-ab95-4251-8aa2-0ead65e097db', NULL, '{}'),
	('b4ba156b-99ba-4157-8b2f-1481f74332bb', 'handwritten-submissions', 'submission_1785999800324.jpg', NULL, '2026-08-06 07:04:25.333961+00', '2026-08-06 07:04:25.333961+00', '2026-08-06 07:04:25.333961+00', '{"eTag": "\"fdac38d0c242300159c24ce568a9b4b3\"", "size": 245805, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T07:04:26.000Z", "contentLength": 245805, "httpStatusCode": 200}', '12a249ad-0eaf-44a6-835c-7ef135cdf621', NULL, '{}'),
	('8cbaceb7-b400-4445-b6f2-40cf0d83c62a', 'handwritten-submissions', 'submission_1786005057612.jpg', NULL, '2026-08-06 08:31:01.40204+00', '2026-08-06 08:31:01.40204+00', '2026-08-06 08:31:01.40204+00', '{"eTag": "\"377f6d9065fbee916b8c1cef1b16fe74\"", "size": 880514, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:31:02.000Z", "contentLength": 880514, "httpStatusCode": 200}', '8a5c90bc-2dc8-43b9-a4ea-281f0514410d', NULL, '{}'),
	('d34b56a6-0c35-4cda-a9a4-2389fba2d0ef', 'handwritten-submissions', 'submission_1786005116616.jpg', NULL, '2026-08-06 08:31:58.464082+00', '2026-08-06 08:31:58.464082+00', '2026-08-06 08:31:58.464082+00', '{"eTag": "\"2b8cabb8b3f44451525f3d55d3a1ef46\"", "size": 907993, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:31:59.000Z", "contentLength": 907993, "httpStatusCode": 200}', 'd1cc05b1-0abb-4954-bfe3-dfdba80fb5cb', NULL, '{}'),
	('ea731d0b-31b6-4ee2-9e9d-8a57414c75af', 'handwritten-submissions', 'submission_1786005188365.jpg', NULL, '2026-08-06 08:33:10.395345+00', '2026-08-06 08:33:10.395345+00', '2026-08-06 08:33:10.395345+00', '{"eTag": "\"c1b206f3f18a9ec22cc4271797555695\"", "size": 836591, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T08:33:11.000Z", "contentLength": 836591, "httpStatusCode": 200}', '4e970e5f-f658-4756-aa97-0decc1fa510e', NULL, '{}'),
	('53ff6da4-d8fe-4e18-a677-187aa9c94335', 'handwritten-submissions', '.emptyFolderPlaceholder', NULL, '2026-08-04 13:14:37.664983+00', '2026-08-04 13:14:37.664983+00', '2026-08-04 13:14:37.664983+00', '{"eTag": "\"d41d8cd98f00b204e9800998ecf8427e\"", "size": 0, "mimetype": "application/octet-stream", "cacheControl": "max-age=3600", "lastModified": "2026-08-04T13:14:37.665Z", "contentLength": 0, "httpStatusCode": 200}', 'f0c32fd1-e783-43ae-a402-7d4dc101618d', NULL, '{}'),
	('184d6430-da6f-4af7-8eff-bc8ac5271f98', 'handwritten-submissions', 'submission_1785902823075.jpg', NULL, '2026-08-05 04:07:21.659122+00', '2026-08-05 04:07:21.659122+00', '2026-08-05 04:07:21.659122+00', '{"eTag": "\"4e95c86a56c5c96f17cb752bf9f7b06e\"", "size": 770565, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T04:07:22.000Z", "contentLength": 770565, "httpStatusCode": 200}', 'd2a44aed-c31a-40d3-8a7f-02921f87bff7', NULL, '{}'),
	('9bd76423-7c1d-4d54-804e-c2a953bc3ea4', 'handwritten-submissions', 'submission_1785906683554.jpg', NULL, '2026-08-05 05:11:26.413287+00', '2026-08-05 05:11:26.413287+00', '2026-08-05 05:11:26.413287+00', '{"eTag": "\"c6e874c4fd706b4748637b0753b55515\"", "size": 717964, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:11:27.000Z", "contentLength": 717964, "httpStatusCode": 200}', 'e09f05a9-36b1-45f2-a62e-43b0f368e5f9', NULL, '{}'),
	('d0d03574-c01a-46e8-87a2-1719c33dde8a', 'handwritten-submissions', 'submission_1785907001911.jpg', NULL, '2026-08-05 05:16:47.731287+00', '2026-08-05 05:16:47.731287+00', '2026-08-05 05:16:47.731287+00', '{"eTag": "\"05a1907b35a299867035ca94e357a54e\"", "size": 726366, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:16:48.000Z", "contentLength": 726366, "httpStatusCode": 200}', 'fa7b4bfd-9844-4479-988f-da82f5cff60f', NULL, '{}'),
	('9e12f544-e0eb-42f5-8d6d-e8d8d07416dd', 'handwritten-submissions', 'submission_1785907079465.jpg', NULL, '2026-08-05 05:18:03.898484+00', '2026-08-05 05:18:03.898484+00', '2026-08-05 05:18:03.898484+00', '{"eTag": "\"584ee6dad34d6d6046b84506b20e33e9\"", "size": 774739, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-05T05:18:04.000Z", "contentLength": 774739, "httpStatusCode": 200}', '32843c04-afef-4182-97af-0ec25c19b6b7', NULL, '{}'),
	('d9bdddf4-7cdc-43f3-928c-9030b7db4451', 'handwritten-submissions', 'submission_1786008147023.jpg', NULL, '2026-08-06 09:22:29.069764+00', '2026-08-06 09:22:29.069764+00', '2026-08-06 09:22:29.069764+00', '{"eTag": "\"f0013eecea33ecb38a2f7acb54b088ba\"", "size": 691743, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T09:22:30.000Z", "contentLength": 691743, "httpStatusCode": 200}', 'e5b51731-0ec2-4184-9a24-b2cae331342a', NULL, '{}'),
	('cf9b4f1e-c619-4d2c-b209-ca7df4ea1de4', 'handwritten-submissions', 'submission_1786008437037.jpg', NULL, '2026-08-06 09:27:24.081966+00', '2026-08-06 09:27:24.081966+00', '2026-08-06 09:27:24.081966+00', '{"eTag": "\"192a20ba501d0f45d3da74e982f420b3\"", "size": 725470, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T09:27:25.000Z", "contentLength": 725470, "httpStatusCode": 200}', '4dd42508-0f56-479f-95f6-3eff41bd2855', NULL, '{}'),
	('9d60bb54-9b44-42e3-9fdb-a04d6ade4775', 'handwritten-submissions', 'submission_1786008513457.jpg', NULL, '2026-08-06 09:28:35.585313+00', '2026-08-06 09:28:35.585313+00', '2026-08-06 09:28:35.585313+00', '{"eTag": "\"b6d88f1841af6ebc1539eba4c85e1f21\"", "size": 699442, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T09:28:36.000Z", "contentLength": 699442, "httpStatusCode": 200}', 'f0c6ba53-85b7-406d-8548-31846fadd833', NULL, '{}'),
	('a5fdb708-2c0b-4305-88cf-e073671cd241', 'handwritten-submissions', 'submission_1786008560297.jpg', NULL, '2026-08-06 09:29:21.94218+00', '2026-08-06 09:29:21.94218+00', '2026-08-06 09:29:21.94218+00', '{"eTag": "\"39e416823a643c82eb77654fe1700a80\"", "size": 634796, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T09:29:22.000Z", "contentLength": 634796, "httpStatusCode": 200}', '65d6e2cd-4014-4b4e-9973-081068cfa5b2', NULL, '{}'),
	('ace7d593-9dcf-4460-80e5-1dd8c377c776', 'handwritten-submissions', 'submission_1786011168605.jpg', NULL, '2026-08-06 10:12:52.73865+00', '2026-08-06 10:12:52.73865+00', '2026-08-06 10:12:52.73865+00', '{"eTag": "\"53dc2998af7884e8210d450a4e085063\"", "size": 775213, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T10:12:53.000Z", "contentLength": 775213, "httpStatusCode": 200}', 'abe2a7da-47f5-41f3-8593-f180fe3a4c21', NULL, '{}'),
	('8d4bcaad-474c-4ab6-a4a7-048a6f8e4dbe', 'handwritten-submissions', 'submission_1786011318345.jpg', NULL, '2026-08-06 10:15:19.99651+00', '2026-08-06 10:15:19.99651+00', '2026-08-06 10:15:19.99651+00', '{"eTag": "\"855826d38f5d6649ff3452b89b88abbd\"", "size": 594975, "mimetype": "image/jpeg", "cacheControl": "max-age=3600", "lastModified": "2026-08-06T10:15:20.000Z", "contentLength": 594975, "httpStatusCode": 200}', '5f89f12c-951c-4597-b780-45d1e5a853bc', NULL, '{}');


--
-- Data for Name: s3_multipart_uploads; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: s3_multipart_uploads_parts; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: vector_indexes; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: supabase_auth_admin
--

SELECT pg_catalog.setval('"auth"."refresh_tokens_id_seq"', 1, false);


--
-- PostgreSQL database dump complete
--

-- \unrestrict 9iZZ1qmESdmtacRfXxaUUZitfnNj2GEucDVGrEn8FaHba7i4JQaWpb5KqL1wWNo

RESET ALL;




SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';


SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."questions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "question_name" "text" NOT NULL,
    "question_text" "text" NOT NULL,
    "model_answer" "text" NOT NULL,
    "test_cases" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "validation_status" "text" DEFAULT 'draft'::"text" NOT NULL,
    "can_publish" boolean DEFAULT false NOT NULL,
    "model_validation_results" "jsonb" DEFAULT '[]'::"jsonb" NOT NULL,
    CONSTRAINT "questions_validation_status_check" CHECK (("validation_status" = ANY (ARRAY['draft'::"text", 'validated'::"text"])))
);


ALTER TABLE "public"."questions" OWNER TO "postgres";


COMMENT ON COLUMN "public"."questions"."validation_status" IS 'Question validation state based on running the model answer against saved Judge0 test cases.';



COMMENT ON COLUMN "public"."questions"."can_publish" IS 'True only when the model answer passes every saved Judge0 test case.';



COMMENT ON COLUMN "public"."questions"."model_validation_results" IS 'Per-test Judge0 validation summary from the latest model answer check.';



CREATE TABLE IF NOT EXISTS "public"."submissions" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "image_url" "text" NOT NULL,
    "student_name" "text",
    "captured_at" timestamp with time zone DEFAULT "now"(),
    "status" "text" DEFAULT 'pending'::"text",
    "extracted_text" "text",
    "verified_at" timestamp with time zone,
    "verified_text" "text"
);


ALTER TABLE "public"."submissions" OWNER TO "postgres";


ALTER TABLE ONLY "public"."questions"
    ADD CONSTRAINT "questions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."submissions"
    ADD CONSTRAINT "submissions_pkey" PRIMARY KEY ("id");



CREATE POLICY "allow public inserts" ON "public"."submissions" USING (true) WITH CHECK (true);



CREATE POLICY "allow public inserts questions" ON "public"."questions" USING (true) WITH CHECK (true);



ALTER TABLE "public"."questions" ENABLE ROW LEVEL SECURITY;


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON TABLE "public"."questions" TO "anon";
GRANT ALL ON TABLE "public"."questions" TO "authenticated";
GRANT ALL ON TABLE "public"."questions" TO "service_role";



GRANT ALL ON TABLE "public"."submissions" TO "anon";
GRANT ALL ON TABLE "public"."submissions" TO "authenticated";
GRANT ALL ON TABLE "public"."submissions" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";








library(deweyr)

api_key <- Sys.getenv("DEWEY_API_KEY")

if (!nzchar(api_key)) {
  stop("DEWEY_API_KEY is not set.")
}

download_dewey_duck(
  api_key = api_key,
  data_id = "prj_37ga6vtz__fldr_btzpw6hub88mzykfi",
  output_dir = "dewey-anthropic-output/deweyr-exact-day",
  partition = NULL,
  where = "
    lower(trim(COMPANY_NAME)) = 'anthropic'
    AND (CASE WHEN length(CAST(START_DATE AS VARCHAR)) = 7
              THEN CAST(START_DATE AS VARCHAR) || '-01'
              ELSE CAST(START_DATE AS VARCHAR) END) >= '2026-04-01'
    AND (CASE WHEN length(CAST(START_DATE AS VARCHAR)) = 7
              THEN CAST(START_DATE AS VARCHAR) || '-01'
              ELSE CAST(START_DATE AS VARCHAR) END) < '2026-10-01'
  ",
  select = c(
    "PERSON_ID",
    "COMPANY_NAME",
    "COMPANY_ID",
    "TITLE_NAME",
    "TITLE_ROLE",
    "TITLE_SUB_ROLE",
    "START_DATE",
    "END_DATE",
    "IS_PRIMARY"
  ),
  overwrite = FALSE,
  batch_size = 10,
  resume = TRUE
)

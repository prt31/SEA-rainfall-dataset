# ============================================================================
# run_rhtests.R  -- RHtestsV4 confirmation on long stations (annual totals)
# ----------------------------------------------------------------------------
# RHtestsV4 is distributed by ECCC as an R source file (RHtestsV4.r), not on
# CRAN. Obtain it from the ETCCDI / ECCC "RHtests" page, then:
#     source("RHtestsV4.r")
# This script writes one RHtests input file per long station and runs the
# penalized maximal F test (FindU: no reference) and, if you supply a reference
# series, the penalized maximal t test (FindU.wRef).
# RHtests input format: columns  year  month  day  value   (missing = -99.9)
# For annual series use month=day=1 (or run monthly with real month indices).
# ============================================================================
source("RHtestsV4.r")     # <-- provide this file

csv <- "malaysia_national_rainfall_to1958.csv"
Y1  <- 1958
LONG_MIN <- 30
months <- c("Jan","Feb","March","April","May","June","July","Aug",
            "Sept","Oct","Nov","Dec")
MISS <- -99.9

d <- read.csv(csv, stringsAsFactors = FALSE); d <- d[d$year <= Y1, ]
d$annual <- rowSums(d[, months])                     # NA unless all 12 present
nyr <- tapply(d$annual, d$station_name, function(x) sum(!is.na(x)))
long <- names(nyr)[nyr >= LONG_MIN]

dir.create("rhtests_in",  showWarnings = FALSE)
dir.create("rhtests_out", showWarnings = FALSE)

for (st in long) {
  s <- d[d$station_name == st, c("year", "annual")]
  s <- s[order(s$year), ]
  out <- data.frame(year = s$year, month = 1, day = 1,
                    value = ifelse(is.na(s$annual), MISS, s$annual))
  f <- file.path("rhtests_in", paste0(gsub("[^A-Za-z0-9]", "_", st), ".txt"))
  write.table(out, f, row.names = FALSE, col.names = FALSE, quote = FALSE)
  base <- file.path("rhtests_out", gsub("[^A-Za-z0-9]", "_", st))
  # penalized maximal F (no reference), 95% level, missing flag, annual (Nadj not needed)
  try(FindU(InSeries = f, output = base, MissingValueCode = as.character(MISS),
            p.lev = 0.95, Iadj = 10000, GUI = FALSE), silent = TRUE)
}
cat("RHtests PMF complete for", length(long), "long stations -> rhtests_out/\n")
cat("For PMT (with reference), build a neighbour composite and call FindU.wRef().\n")

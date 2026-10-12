# ============================================================================
# run_climatol.R  -- genuine Climatol homogenization of the pre-1958 archive
# Requires a machine with CRAN access:  install.packages("climatol")
# Mirrors the pipeline parameters used in the Python implementation.
# ============================================================================
# INPUT : malaysia_national_rainfall_to1958.csv  (wide: station-year x 12 months)
# OUTPUT: Prcp_1875-1958.dat/.est  + climatol homogenization products & PDFs
# ----------------------------------------------------------------------------
library(climatol)

csv <- "malaysia_national_rainfall_to1958.csv"
Y0 <- 1875; Y1 <- 1958
months <- c("Jan","Feb","March","April","May","June","July","Aug",
            "Sept","Oct","Nov","Dec")

d <- read.csv(csv, stringsAsFactors = FALSE)
d <- d[d$year <= Y1, ]

# ---- station table (one row per station) ----
st <- aggregate(cbind(lon_decimal, lat_decimal, elevation_m) ~ station_name,
                data = d, FUN = function(x) median(x, na.rm = TRUE), na.action = na.pass)
st$elevation_m[is.na(st$elevation_m)] <- 0
stations <- st$station_name
ne <- length(stations)

# ---- build the (time x station) monthly matrix on the common frame ----
yrs   <- Y0:Y1
nyr   <- length(yrs)
nd    <- nyr * 12                       # 1008 monthly slots per station
mat   <- matrix(NA_real_, nrow = nd, ncol = ne)   # rows = time (year-major), cols = station
rowid <- function(y, m) (y - Y0) * 12 + m
for (i in seq_len(nrow(d))) {
  s <- match(d$station_name[i], stations)
  y <- d$year[i]
  for (m in 1:12) mat[rowid(y, m), s] <- d[i, months[m]]
}

# ---- write climatol input files (station-major vector + .est) ----
# .dat : column = station, filled column-major -> write matrix as-is
write(mat, file = sprintf("Prcp_%d-%d.dat", Y0, Y1))
est <- data.frame(X = st$lon_decimal, Y = st$lat_decimal, Z = st$elevation_m,
                  CODE = sprintf("S%03d", seq_len(ne)), NAME = stations)
write.table(est, file = sprintf("Prcp_%d-%d.est", Y0, Y1),
            row.names = FALSE, col.names = FALSE,
            quote = c(FALSE, FALSE, FALSE, TRUE, TRUE))

# ---- run homogenization ----
# std = 2  -> ratio normalization (recommended for precipitation)
# dz.max   -> anomaly outlier tolerance; wd -> distance weighting (km); nref neighbours
homogen("Prcp", Y0, Y1,
        std   = 2,          # precipitation: normalize by the ratio to the mean
        nref  = 10,         # up to 10 nearest neighbours for the reference
        dz.max = 6,         # flag/adjust anomalies beyond this (keeps real extremes)
        wd    = c(0, 60, 60),   # distance weighting (km) for the reference
        snht1 = 25, snht2 = 25, # SNHT thresholds (stepped-window, whole-series)
        expl  = TRUE)       # exploratory diagnostics + PDFs

# ---- extract products ----
# Homogenized + infilled series and break list are written by homogen();
# summarize monthly series and break inventory:
dahstat("Prcp", Y0, Y1, stat = "series")   # writes homogenized series to CSV
dahstat("Prcp", Y0, Y1, stat = "mean")     # station means
cat("Climatol run complete. See Prcp_1875-1958*.pdf / *.csv for breaks & series.\n")

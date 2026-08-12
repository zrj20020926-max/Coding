from prometheus_client import Counter

AI_ANALYSIS_REQUESTS = Counter(
    "codearena_ai_analysis_requests_total",
    "AI analysis API requests",
    ["outcome"],
)
AI_ANALYSIS_CACHE_HITS = Counter(
    "codearena_ai_analysis_cache_hits_total",
    "AI analysis result cache hits",
)
AI_ANALYSIS_QUOTA_REJECTIONS = Counter(
    "codearena_ai_analysis_quota_rejections_total",
    "AI analysis quota rejections",
    ["reason"],
)

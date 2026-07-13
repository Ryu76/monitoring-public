from pydantic import BaseModel

class DashboardSummaryData(BaseModel):
    total_servers: int
    normal: int
    warning: int
    critical: int

class DashboardSummaryResponse(BaseModel):
    success: bool
    code: str
    data: DashboardSummaryData

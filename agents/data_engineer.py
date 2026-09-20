from pydantic_ai import Agent, RunContext, Tool
import asyncpg
from typing import List, Optional
from core.dependencies import DataEngineDependencies
from core.settings import settings
from prompts.persona import DATA_ENGINEER_PERSONA
from core.observability import log_and_handle_error

# Initialize the Data Engineer Agent
data_engineer_agent = Agent(
    model=settings.get_model(),
    deps_type=DataEngineDependencies,
    system_prompt=DATA_ENGINEER_PERSONA,
    retries=2
)

@data_engineer_agent.tool
@log_and_handle_error
async def run_sql_query(ctx: RunContext[DataEngineDependencies], query: str) -> str:
    """
    Execute a READ-ONLY SQL query (SELECT) to inspect schema or data.
    SAFE operation.
    """
    if "drop" in query.lower() or "delete" in query.lower() or "update" in query.lower() or "insert" in query.lower() or "alter" in query.lower() or "create" in query.lower():
         return "❌ SECURITY ALERT: This tool is for READ-ONLY queries. Use 'execute_ddl' or 'execute_dml' for modifications."
         
    async with ctx.deps.pool.acquire() as conn:
        rows = await conn.fetch(query)
        if not rows:
            return "No results found."
        
        # Format as simple text table
        if len(rows) > 0:
            headers = rows[0].keys()
            res = " | ".join(headers) + "\n" + "-" * 50 + "\n"
            for row in rows:
                res += " | ".join([str(val) for val in row.values()]) + "\n"
            return res
    return "Query executed."

@data_engineer_agent.tool
@log_and_handle_error
async def execute_ddl(ctx: RunContext[DataEngineDependencies], query: str, justification: str) -> str:
    """
    Execute DDL statements (CREATE, ALTER, DROP) to modify schema.
    RISKY operation. Requires justification.
    """
    # Basic safety check
    forbidden = ["drop table expenses", "drop table income"] # Hardcoded safety rails
    if any(bad in query.lower() for bad in forbidden):
        return f"❌ SAFETY BLOCK: The query '{query}' is flagged as destructive to core financial data."

    try:
        async with ctx.deps.pool.acquire() as conn:
            await conn.execute(query)
        return f"✅ DDL Executed successfully: {query}"
    except Exception as e:
        return f"❌ SQL Error: {str(e)}"

@data_engineer_agent.tool
@log_and_handle_error
async def execute_dml(ctx: RunContext[DataEngineDependencies], query: str) -> str:
    """
    Execute DML statements (INSERT, UPDATE, DELETE).
    """
    try:
        async with ctx.deps.pool.acquire() as conn:
            result = await conn.execute(query)
        return f"✅ DML Executed: {result}"
    except Exception as e:
        return f"❌ SQL Error: {str(e)}"

@data_engineer_agent.tool
@log_and_handle_error
async def inspect_table_schema(ctx: RunContext[DataEngineDependencies], table_name: str) -> str:
    """
    Get column details for a specific table.
    """
    query = """
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = $1
    ORDER BY ordinal_position;
    """
    async with ctx.deps.pool.acquire() as conn:
        rows = await conn.fetch(query, table_name)
        if not rows:
            return f"Table '{table_name}' not found."
        
        res = f"SCHEMA: {table_name}\n"
        res += "Column | Type | Nullable | Default\n"
        for r in rows:
            res += f"{r['column_name']} | {r['data_type']} | {r['is_nullable']} | {r['column_default']}\n"
        return res

@data_engineer_agent.tool
async def validate_financial_integrity(ctx: RunContext[DataEngineDependencies]) -> str:
    """
    Run a health check on the financial ledger (e.g. checking for negative amounts).
    """
    # 1. Check for negative amounts in Income (should be positive)
    q1 = "SELECT count(*) FROM income WHERE amount < 0"
    # 2. Check for negative amounts in Expenses (should be positive generally, unless refund?)
    q2 = "SELECT count(*) FROM expenses WHERE amount < 0"
    
    async with ctx.deps.pool.acquire() as conn:
        neg_income = await conn.fetchval(q1)
        neg_expense = await conn.fetchval(q2)
        
    report = "Health Check Report:\n"
    if neg_income > 0:
        report += f"⚠️ FOUND {neg_income} income records with negative amounts! This violates accounting principles.\n"
    else:
        report += "✅ Income Integrity: OK\n"
        
    if neg_expense > 0:
        report += f"⚠️ FOUND {neg_expense} expense records with negative amounts! (Could be refunds, please verify).\n"
    else:
        report += "✅ Expense Integrity: OK\n"
        
    return report

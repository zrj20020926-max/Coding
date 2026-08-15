from __future__ import annotations

import re
from typing import Any

from app.domain import AIAnalysisOutput, DiagnosticFinding


def _detected(summary: str) -> DiagnosticFinding:
    return DiagnosticFinding(detected=True, summary=summary)


def _problem_text(safe_input: dict[str, Any]) -> str:
    exercise = safe_input.get("exercise")
    if not isinstance(exercise, dict):
        return ""
    return "\n".join(str(value) for value in exercise.values()).casefold()


def apply_static_diagnostics(
    output: AIAnalysisOutput, safe_input: dict[str, Any]
) -> AIAnalysisOutput:
    """Reinforce model output with deterministic JavaScript ACM I/O checks.

    Rules only inspect already-allowlisted public content, runtime and the owner's source.
    They never read test data and cannot influence the submission state.
    """

    runtime = str(safe_input.get("runtime") or "")
    source = str(safe_input.get("source_code") or "")
    problem_text = _problem_text(safe_input)
    findings: dict[str, DiagnosticFinding] = {}
    suggestions: list[str] = []

    if runtime == "javascript-v8" and re.search(
        r"\brequire\s*\(|\bprocess(?:\.|\[)|\bBuffer\b", source
    ):
        findings["runtime_mismatch"] = _detected(
            "JavaScript V8 模式中出现了 Node.js 专属的 require、process 或 Buffer API。"
        )
        suggestions.append("V8 模式只使用 readline() 读取输入，并使用 print() 输出。")
    elif runtime == "nodejs" and re.search(r"\breadline\s*\(|\bprint\s*\(", source):
        findings["runtime_mismatch"] = _detected(
            "Node.js 模式中出现了 V8 专属的 readline() 或 print() API。"
        )
        suggestions.append("Node.js 模式使用 fs.readFileSync(0, 'utf8') 和标准输出 API。")

    missing_reader = (
        runtime == "javascript-v8" and not re.search(r"\breadline\s*\(", source)
    ) or (
        runtime == "nodejs" and not re.search(r"readFileSync\s*\(\s*0\s*,", source)
    )
    if missing_reader:
        findings["input_reading_issue"] = _detected(
            "源码中没有找到与当前运行模式匹配的标准输入读取入口。"
        )

    direct_trim = bool(
        re.search(r"readFileSync\s*\([^)]*\)\s*\.trim\s*\(", source)
    )
    empty_sensitive = any(
        marker in problem_text for marker in ("空输入", "空行", "原始", "保留空格", "末尾换行")
    )
    if runtime == "nodejs" and (direct_trim or (".trim()" in source and empty_sensitive)):
        findings["input_reading_issue"] = _detected(
            "Node.js 原始输入被无条件 trim()，空输入、空行或边界空白可能因此丢失。"
        )
        findings["whitespace_issue"] = _detected(
            "无条件 trim() 改变了 stdin 的首尾空白语义。"
        )
        suggestions.append("先保留 raw 输入，再根据题目格式决定是否使用 trimEnd() 或 trim()。")

    if re.search(r"\.split\(\s*(['\"]) \1\s*\)", source):
        findings["token_parsing_issue"] = _detected(
            "split(' ') 会在连续空格时产生空 token，也无法正确处理制表符。"
        )
        findings["whitespace_issue"] = _detected(
            "token 解析只识别单个普通空格，未覆盖通用空白字符。"
        )
        suggestions.append(
            "若题目按空白分隔 token，使用 trim 后的 split(/\\s+/) 或 match(/\\S+/g)。"
        )

    splits_lf_only = bool(re.search(r"\.split\(\s*(['\"])\\n\1\s*\)", source))
    handles_crlf = bool(re.search(r"\\r\?\\n|replace\s*\([^)]*\\r", source))
    if runtime == "nodejs" and splits_lf_only and not handles_crlf:
        findings["line_parsing_issue"] = _detected(
            "源码只按 LF 拆行，CRLF 输入可能在每行末尾残留回车字符。"
        )
        suggestions.append("按行解析时使用 split(/\\r?\\n/)，并按题意保留空行。")

    truthy_readline = re.search(
        r"while\s*\(\s*\(?\s*\w+\s*=\s*readline\s*\(\s*\)\s*\)?\s*\)", source
    )
    unbounded_line_cursor = re.search(
        r"while\s*\(\s*true\s*\)|for\s*\(\s*;\s*;\s*\)", source
    ) and re.search(r"\w+\s*\[\s*\w+\+\+\s*\]", source)
    if truthy_readline or unbounded_line_cursor:
        findings["eof_issue"] = _detected(
            "EOF 循环缺少明确边界：空行可能被当作 EOF，或行游标可能越过数组末尾。"
        )
        suggestions.append("V8 显式比较 undefined；Node.js 行游标先检查 index < lines.length。")

    bigint_number_mix = re.search(
        r"(?:\b\d+n|BigInt\s*\([^)]*\))\s*[+\-*/%]\s*(?:\d+(?!n\b)|Number\s*\()|"
        r"(?:\d+(?!n\b)|Number\s*\([^)]*\))\s*[+\-*/%]\s*(?:\d+n\b|BigInt\s*\()",
        source,
    )
    bigint_variables = re.findall(
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*BigInt\s*\(", source
    )
    if not bigint_number_mix:
        bigint_number_mix = next(
            (
                match
                for variable in bigint_variables
                if (
                    match := re.search(
                        rf"\b{re.escape(variable)}\s*[+\-*/%]\s*\d+(?!n\b)|"
                        rf"\d+(?!n\b)\s*[+\-*/%]\s*\b{re.escape(variable)}\b",
                        source,
                    )
                )
            ),
            None,
        )
    needs_bigint = any(
        marker in problem_text
        for marker in ("bigint", "安全整数", "2^53", "2 的 53", "超过 number")
    )
    if bigint_number_mix:
        findings["numeric_issue"] = _detected(
            "源码把 BigInt 与 Number 直接参与同一算术运算，会抛出 TypeError。"
        )
        suggestions.append("同一表达式中的整数统一为 BigInt，并在输出时调用 toString()。")
    elif needs_bigint and re.search(r"\bNumber\s*\(", source) and "BigInt(" not in source:
        findings["numeric_issue"] = _detected(
            "练习包含超出 Number 安全整数范围的数据，但源码仍使用 Number 转换。"
        )

    debug_output = re.search(
        r"(?:console\.log|print)\s*\(\s*(['\"])(?:debug|answer|result|请输入|调试|答案)",
        source,
        re.IGNORECASE,
    )
    array_debug = re.search(r"console\.log\s*\(\s*\[[^)]*\]\s*\)", source)
    if debug_output or array_debug:
        findings["output_format_issue"] = _detected(
            "stdout 可能包含调试文字或 JavaScript 数组调试格式，而不是题目要求的精确文本。"
        )
        suggestions.append("stdout 只输出答案；数组使用 join() 明确控制分隔符。")

    has_loop = bool(re.search(r"\b(?:for|while)\s*\(", source))
    repeated_shift = has_loop and ".shift(" in source
    output_in_loop = has_loop and bool(re.search(r"(?:console\.log|print)\s*\(", source))
    repeated_concat = has_loop and bool(re.search(r"\b(?:out|result|answer)\s*\+=", source))
    if repeated_shift or output_in_loop or repeated_concat:
        findings["performance_issue"] = _detected(
            "大输入下存在循环内 shift()、频繁输出或反复字符串拼接的潜在线性放大问题。"
        )
        suggestions.append("使用索引游标解析，并用数组收集结果后统一 join 输出。")

    data = output.model_dump()
    for field_name, finding in findings.items():
        data[field_name] = finding.model_dump()
    merged_suggestions = list(output.suggestions)
    for suggestion in suggestions:
        if suggestion not in merged_suggestions and len(merged_suggestions) < 8:
            merged_suggestions.append(suggestion)
    data["suggestions"] = merged_suggestions
    return AIAnalysisOutput.model_validate(data)

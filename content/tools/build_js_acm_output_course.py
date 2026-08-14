# ruff: noqa
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROBLEM_ROOT = ROOT / "problems" / "js-acm-output"
REFERENCE_ROOT = ROOT / "reference-solutions" / "js-acm-output"
TEST_ROOT = ROOT / "test-data" / "js-acm-output"

SCENARIOS = (
    ("minimum_boundary", "最小边界"),
    ("normal", "普通输出"),
    ("duplicates", "重复值下的空格与换行边界"),
    ("special_structure", "特殊字符或格式结构"),
    ("performance", "固定规模批量输出"),
    ("counterexample", "常见 Wrong Answer 反例"),
)
SCORES = (10, 15, 15, 20, 20, 20)


def write_utf8(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value.encode("utf-8"))


@dataclass(frozen=True)
class Task:
    slug: str
    title: str
    chapter: str
    mode: str
    family: str
    objective: str
    exact_rule: str
    minutes: int = 8


@dataclass(frozen=True)
class Chapter:
    slug: str
    title: str
    description: str
    tasks: tuple[tuple[str, str, str, str, str, str], ...]


CHAPTERS = (
    Chapter(
        "js-acm-output-basics",
        "输出课程一：基础输出",
        "掌握单值、固定文本、空行和最终换行等 stdout 基础契约。",
        (
            ("one-integer", "输出一个整数", "one-integer", "integer", "把整数转换为十进制文本。", "只输出规范十进制整数。"),
            ("one-string", "输出一个字符串", "one-string", "text", "原样输出指定字符串。", "字符串正文必须与输入首行一致。"),
            ("values-single-space", "多个值以空格分隔", "values-space", "tokens", "使用一个空格连接多个值。", "相邻值之间必须恰好一个空格。"),
            ("value-per-line", "每个值单独一行", "values-lines", "tokens", "使用换行分隔多个值。", "每个值独占一行，不能用空格代替换行。"),
            ("fixed-text", "输出固定文本", "fixed-text", "ignored", "输出与输入无关的固定文本。", "必须精确输出 Hello, CodeArena!。"),
            ("no-extra-prompt", "不输出额外提示语", "sum-no-prompt", "pair", "只输出计算结果，不输出提示语。", "只输出两数之和，不得出现 result: 等前缀。"),
            ("negative-number", "输出负数", "negative-number", "integer", "正确输出负号与数值。", "输出输入绝对值对应的负整数。"),
            ("bigint-without-suffix", "输出 BigInt", "bigint", "bigint", "将 BigInt 转成不带后缀的十进制文本。", "不得带 JavaScript 调试表示中的 n 后缀。"),
            ("internal-empty-line", "输出空行", "empty-line", "two-lines", "在两段文本之间输出一个空行。", "两段文本之间必须恰好有一个内部空行。"),
            ("terminal-newline", "输出末尾换行", "terminal-newline", "text", "理解 print 与 stdout.write 的最终换行差异。", "参考实现追加一个换行；exact checker 接受缺少最终换行。"),
        ),
    ),
    Chapter(
        "js-acm-output-arrays",
        "输出课程二：数组输出",
        "练习 join、逐行输出、二维数组和 BigInt/浮点数组的稳定格式。",
        (
            ("array-space-join", "数组使用空格连接", "array-space", "array", "使用 join(' ') 输出数组。", "元素之间恰好一个空格。"),
            ("array-comma-join", "数组使用逗号连接", "array-comma", "array", "使用逗号连接数组元素。", "元素之间只能有逗号，不附加空格。"),
            ("array-one-per-line", "数组每行一个元素", "array-lines", "array", "逐行表示数组元素。", "每个元素独占一行。"),
            ("array-length-first", "数组前输出长度", "array-length", "array", "先输出长度，再输出数组。", "第一行为长度，第二行为单空格连接的数组。"),
            ("array-reverse", "数组逆序输出", "array-reverse", "array", "在不产生额外标点的情况下逆序输出。", "逆序元素以一个空格连接。"),
            ("matrix-row-output", "二维数组逐行输出", "matrix-rows", "matrix", "将二维数组按行输出。", "每行列值以一个空格连接。"),
            ("character-array-compact", "字符数组无分隔输出", "chars-compact", "array", "把字符数组拼成连续字符串。", "字符之间不得出现空格或逗号。"),
            ("empty-array-rule", "空数组输出规则", "array-empty", "array", "为长度为零的数组输出明确标记。", "空数组输出 EMPTY，非空数组正常连接。"),
            ("bigint-array-output", "BigInt 数组输出", "array-bigint", "bigint-array", "逐个字符串化 BigInt。", "所有元素都不得带 n 后缀。"),
            ("float-array-output", "浮点数组输出", "array-float", "float-array", "统一浮点数组的小数位。", "每个元素固定两位小数并以一个空格连接。"),
        ),
    ),
    Chapter(
        "js-acm-output-groups",
        "输出课程三：多组结果",
        "组织 Case 前缀、组间空行、多行分组和大批量结果。",
        (
            ("group-one-line", "每组一行", "group-lines", "groups", "每组计算一个简单结果并独占一行。", "输出行数必须等于测试组数。"),
            ("case-hash-format", "Case #1: result", "case-hash", "groups", "输出带井号的 Case 编号。", "格式必须为 Case #x: result。"),
            ("case-plain-format", "Case 1: result", "case-plain", "groups", "输出不带井号的 Case 编号。", "格式必须为 Case x: result。"),
            ("blank-between-groups", "组间空行", "group-blank", "groups", "在相邻组之间插入空行。", "组与组之间恰好一个空行。"),
            ("group-multiple-lines", "每组输出多行", "group-multiline", "groups", "每组输出结果与元素个数两行。", "每组两行，相邻组直接衔接。"),
            ("group-title-first", "每组先输出标题", "group-title", "groups", "为每组添加独立标题行。", "标题格式为 Group x，下一行输出结果。"),
            ("no-blank-after-last-group", "最后一组后不增加额外空行", "group-no-tail-blank", "groups", "用 join 控制组间空行。", "只在组之间插入空行；最终空白依 checker 规则忽略。"),
            ("many-results-buffer", "大量结果缓冲后输出", "group-buffer", "many-groups", "先收集大量结果再一次写入 stdout。", "每个结果一行，不得出现调试文本。", 12),
        ),
    ),
    Chapter(
        "js-acm-output-numbers",
        "输出课程四：数值格式",
        "掌握小数位、百分比、科学计数法、补零和大整数文本化。",
        (
            ("fixed-two-decimals", "固定两位小数", "fixed-two", "float", "使用 toFixed(2) 输出。", "即使是整数也必须保留两位小数。"),
            ("fixed-n-decimals", "固定 n 位小数", "fixed-n", "float-n", "按输入位数动态控制小数位。", "小数位数必须恰好等于 n。"),
            ("percentage-format", "百分比", "percentage", "float", "把比例转换为百分比文本。", "乘以 100，保留两位小数并追加 %。"),
            ("scientific-notation", "科学计数法", "scientific", "float", "使用统一科学计数法。", "使用三位小数的 e 记法。"),
            ("leading-zero", "前导零", "leading-zero", "number-width", "按固定宽度补前导零。", "宽度不足时在数字左侧补 0。"),
            ("explicit-plus-sign", "正数前加加号", "plus-sign", "integer", "为正数显式添加加号。", "正数前加 +，零和负数不加。"),
            ("decimal-rounding", "四舍五入", "round-two", "float", "稳定四舍五入到两位小数。", "输出四舍五入后的两位小数。"),
            ("floating-error-format", "避免浮点误差导致格式错误", "safe-sum", "float-pair", "用最终格式化隐藏二进制浮点尾差。", "两数之和固定输出两位小数。"),
            ("large-integer-text", "大整数输出", "bigint", "bigint", "安全输出超出 Number 范围的大整数。", "按十进制输出且不得出现 n。"),
            ("negative-zero", "-0 的处理", "negative-zero", "float", "把 -0 规范化为 0.00。", "任何负零表示都输出 0.00。"),
        ),
    ),
    Chapter(
        "js-acm-output-alignment",
        "输出课程五：表格和对齐",
        "使用 padStart、padEnd 构建等宽字段，并理解 Unicode 显示宽度边界。",
        (
            ("right-align", "固定宽度右对齐", "right-align", "width-text", "使用 padStart 右对齐文本。", "输出总宽度等于给定宽度。"),
            ("left-align", "固定宽度左对齐", "left-align", "width-text", "使用 padEnd 左对齐文本。", "右侧补足到指定宽度后输出 | 边界符。"),
            ("number-zero-padding", "数字补零", "leading-zero", "number-width", "用 padStart 为数字补零。", "负号保留在最左侧，数值部分补零。"),
            ("simple-table", "简单表格", "simple-table", "records", "输出姓名与分数两列表格。", "姓名左对齐 10 列，分数右对齐 5 列。"),
            ("aligned-matrix", "矩阵对齐", "matrix-align", "matrix", "按矩阵最大字段宽度右对齐。", "所有列使用统一宽度并以一个空格分隔。"),
            ("header-separator", "表头和分隔线", "header-line", "headers", "输出表头和等长分隔线。", "第二行连字符数量与第一行字符数一致。"),
            ("variable-string-alignment", "不同长度字符串对齐", "strings-align", "string-list", "按最长字符串的代码点长度左对齐。", "冒号前字段宽度一致。"),
            ("unicode-alignment-limit", "Unicode 对齐限制", "unicode-width", "string-list", "区分代码点长度与终端显示宽度。", "输出 codePoints:length:text，不声称等宽显示。"),
        ),
    ),
    Chapter(
        "js-acm-output-strings",
        "输出课程六：字符串格式",
        "练习拼接、转义、制表符、多行文本、Unicode 和 JSON 序列化。",
        (
            ("string-concatenation", "拼接字符串", "concat", "two-lines", "使用明确分隔符拼接两行。", "输出 first-second。"),
            ("template-string", "模板字符串", "template", "name-age", "使用模板字符串组合不同类型字段。", "格式为 name is age years old.。"),
            ("preserve-output-spaces", "保留输入中的空格", "one-string", "text-spaces", "输出时不 trim 原始文本。", "行首、行中空格属于正文。"),
            ("output-backslash", "输出反斜杠", "backslash", "path", "正确转义并输出反斜杠。", "把斜杠路径转换为 Windows 风格反斜杠。"),
            ("output-quotes", "输出引号", "quotes", "text", "在文本两侧输出双引号。", "输出包含实际双引号，不输出转义源码。"),
            ("output-tabs", "输出制表符", "tabs", "tokens", "使用真实制表符分隔字段。", "字段之间必须是 TAB，不是多个空格。"),
            ("output-multiline-text", "输出多行文本", "multiline", "three-lines", "保持三行文本的行结构。", "输出顺序和换行结构必须与输入一致。"),
            ("output-unicode", "输出 Unicode", "one-string", "unicode", "完整输出中文和表情符号。", "不得按字节截断或转义 Unicode。"),
            ("json-stringify-use", "JSON.stringify 的正确使用场景", "json", "json", "安全解析并输出紧凑 JSON。", "输出合法紧凑 JSON，不使用 eval。"),
            ("no-debug-output", "禁止额外调试输出", "sum-no-prompt", "pair", "确保 stdout 只包含正式答案。", "任何 debug、input= 前缀都会 Wrong Answer。"),
        ),
    ),
    Chapter(
        "js-acm-output-performance",
        "输出课程七：输出性能",
        "用数组与 join 批量输出，理解 stdout 限制、时间和内存权衡。",
        (
            ("avoid-loop-console-log", "循环内 console.log 的性能问题", "range-lines", "count", "避免在循环内频繁调用 console.log。", "输出 1 到 n，每行一个数。", 12),
            ("collect-output-array", "使用数组收集输出", "squares-lines", "count", "把结果先 push 到数组。", "输出 1 到 n 的平方，每行一个。", 12),
            ("join-newlines-once", "最后使用 join('\\n')", "range-lines", "count", "使用一次 join 生成多行文本。", "结果行之间只有一个换行。", 12),
            ("stdout-write-once", "使用 process.stdout.write()", "double-lines", "count", "Node.js 中一次写出缓冲结果。", "输出 1 到 n 的两倍，每行一个。", 12),
            ("v8-batch-print", "V8 中批量拼接后 print()", "triple-lines", "count", "V8 中一次 print 整个结果。", "输出 1 到 n 的三倍，每行一个。", 12),
            ("large-output-memory-tradeoff", "大量输出的内存权衡", "indexed-lines", "count", "控制数组元素大小并避免重复拼接。", "格式为 index:value，每行一项。", 15),
            ("output-limit-contract", "输出限制处理", "bounded-lines", "count", "根据题面上限避免制造失控输出。", "n 不超过 10000 时逐行输出；超过时输出 OUTPUT_TOO_LARGE。", 15),
        ),
    ),
)


def build_tasks() -> list[Task]:
    tasks: list[Task] = []
    for chapter in CHAPTERS:
        for raw in chapter.tasks:
            suffix, title, mode, family, objective, rule, *minutes = raw
            tasks.append(
                Task(
                    slug=f"js-acm-output-{suffix}",
                    title=title,
                    chapter=chapter.slug,
                    mode=mode,
                    family=family,
                    objective=objective,
                    exact_rule=rule,
                    minutes=minutes[0] if minutes else 8,
                )
            )
    return tasks


def cases_for(family: str) -> list[str]:
    fixed: dict[str, list[str]] = {
        "ignored": ["", "ignored\n", "0\n", "中文\n", "x y\n", "debug\n", "-1\n", "end"],
        "integer": ["7\n", "12\n", "0\n", "42\n", "999999\n", "1\n", "8\n", "100\n"],
        "bigint": ["9007199254740993\n", "123456789012345678901234567890\n", "0\n", "-9007199254740995\n", "9" * 5000 + "\n", "10000000000000000001\n", "-1\n", "99999999999999999999"],
        "text": ["hello\n", "CodeArena\n", "a b\n", "中文输出\n", "emoji🙂\n", "x\n", "quote\"\n", "done"],
        "text-spaces": ["  hello world\n", "a  b\n", " leading\n", "中 文\n", " " * 100 + "x\n", "tail  \n", "\tvalue\n", " both "],
        "unicode": ["你好\n", "🙂ACM\n", "中文 输出\n", "é漢字\n", "🙂" * 200 + "\n", "����野家\n", "a🙂b\n", "终点"],
        "tokens": ["1 2 3\n", "alpha beta\n", "x\n", "a b c d\n", "0 0 0 0 0\n", "left middle right\n", "A B\n", "9 8 7"],
        "pair": ["1 2\n", "7 -3\n", "0 0\n", "100 200\n", "999999 1\n", "-8 -9\n", "42 58\n", "5 6"],
        "two-lines": ["left\nright\n", "A\nB\n", "\ntext\n", "中文\n🙂\n", "x" * 1000 + "\ny\n", "first\nlast\n", "one\ntwo\n", "up\ndown"],
        "three-lines": ["a\nb\nc\n", "one\ntwo\nthree\n", "\nmid\nend\n", "中\n文\n🙂\n", "x" * 1000 + "\ny\nz\n", "1\n2\n3\n", "left\n\nright\n", "A\nB\nC"],
        "array": ["3\n1 2 3\n", "4\na b c d\n", "0\n\n", "5\n-1 -1 2 2 3\n", "1000\n" + " ".join(str(i) for i in range(1000)) + "\n", "2\n9007199254740993 9007199254740995\n", "1\nx\n", "3\n7 8 9"],
        "bigint-array": ["3\n1 2 3\n", "2\n9007199254740993 9007199254740995\n", "0\n\n", "4\n-1 0 1 99999999999999999999\n", "1000\n" + " ".join(str(10**18 + i) for i in range(1000)) + "\n", "2\n-9007199254740999 9007199254740999\n", "1\n0\n", "3\n7 8 9"],
        "float-array": ["3\n1 2.5 3.14159\n", "2\n-0 9.999\n", "0\n\n", "4\n0.1 0.2 0.3 0.4\n", "1000\n" + " ".join("1.25" for _ in range(1000)) + "\n", "2\n999.995 -4.444\n", "1\n8\n", "3\n-1.5 0 1.5"],
        "matrix": ["2 2\n1 2\n3 4\n", "1 3\n7 8 9\n", "1 1\n0\n", "3 2\n-1 20\n300 4\n5 60\n", "50 20\n" + "\n".join(" ".join(str((r + c) % 100) for c in range(20)) for r in range(50)) + "\n", "2 3\n1 1 1\n2 2 2\n", "2 1\n9\n10\n", "2 2\n1000 -2\n30 4"],
        "groups": ["2\n1 2\n3 4\n", "3\n5\n1 2 3\n-1 -2\n", "1\n0\n", "4\n1 1\n2 2\n3 3\n4 4\n", "1000\n" + "\n".join(f"{i} {i + 1}" for i in range(1000)) + "\n", "2\n9 9 9\n-3\n", "2\n100\n200\n", "3\n7 8\n9\n10 11"],
        "float": ["3.14159\n", "2\n", "-0\n", "0.125\n", "999999.995\n", "-1.005\n", "0.1\n", "42.5"],
        "float-n": ["3.14159 2\n", "2 4\n", "-0 3\n", "0.125 1\n", "999.999 0\n", "-1.005 2\n", "0.1 8\n", "42.5 3"],
        "float-pair": ["0.1 0.2\n", "1.25 2.75\n", "-0.1 0.1\n", "999.99 0.01\n", "12345.67 76543.21\n", "-1.005 2.005\n", "0 0\n", "3.333 6.667"],
        "number-width": ["7 4\n", "42 6\n", "0 3\n", "-7 5\n", "123456 3\n", "9 10\n", "88 2\n", "5 1"],
        "width-text": ["6 cat\n", "10 Code\n", "1 x\n", "8 中文\n", "100 " + "x" * 50 + "\n", "5 abcde\n", "4 a\n", "7 done"],
        "records": ["2\nAlice 7\nBob 42\n", "1\nCodeArena 100\n", "0\n", "3\nA 1\nLongName 20\nC 300\n", "100\n" + "\n".join(f"user{i} {i}" for i in range(100)) + "\n", "2\n中文 8\nJS 9\n", "1\nX -1\n", "2\nA 0\nB 0"],
        "headers": ["Name Score\n", "A B\n", "X\n", "First Second Third\n", ("H" * 1000) + "\n", "中文 标题\n", "left right\n", "One Two"],
        "string-list": ["3\na\nlong\nmid\n", "2\n猫\nCode\n", "0\n", "4\nx\nyy\nzzz\nwwww\n", "100\n" + "\n".join("x" * (i % 20 + 1) for i in range(100)) + "\n", "3\n🙂\n中a\nabc\n", "1\nonly\n", "2\nA\nBBBB"],
        "name-age": ["Alice 18\n", "Bob 0\n", "张三 20\n", "A 99\n", ("x" * 1000) + " 1\n", "JS 12\n", "Kid 7\n", "End 42"],
        "path": ["usr/local/bin\n", "a/b/c\n", "single\n", "C/temp/file.txt\n", "/".join("x" for _ in range(1000)) + "\n", "中文/目录\n", "a//b\n", "root/end"],
        "json": ["{\"name\":\"Ada\",\"score\":7}\n", "[1,2,3]\n", "null\n", "{\"text\":\"中文\",\"ok\":true}\n", "[" + ",".join(str(i) for i in range(1000)) + "]\n", "{\"space\":\"a b\"}\n", "\"hello\"\n", "{\"nested\":{\"x\":1}}"],
        "count": ["5\n", "3\n", "0\n", "10\n", "20000\n", "1000\n", "1\n", "10000"],
    }
    if family == "many-groups":
        counts = (3, 1, 0, 10, 5000, 100, 2, 1000)
        return [str(n) + "\n" + "\n".join(str(i) for i in range(n)) + ("\n" if n else "") for n in counts]
    try:
        values = fixed[family]
    except KeyError:
        raise RuntimeError(f"unknown case family: {family}") from None
    if len(values) != 8:
        raise RuntimeError(f"case family {family} must contain eight cases")
    return values


SOLVERS: dict[str, str] = {
    "one-integer": "output = String(Number(tokens[0] ?? 0));",
    "one-string": "output = lines[0] ?? '';",
    "values-space": "output = tokens.join(' ');",
    "values-lines": "output = tokens.join('\\n');",
    "fixed-text": "output = 'Hello, CodeArena!';",
    "sum-no-prompt": "output = String(Number(tokens[0] ?? 0) + Number(tokens[1] ?? 0));",
    "negative-number": "output = (-BigInt(tokens[0] ?? '0')).toString();",
    "bigint": "output = BigInt(tokens[0] ?? '0').toString();",
    "empty-line": "output = `${lines[0] ?? ''}\\n\\n${lines[1] ?? ''}`;",
    "terminal-newline": "output = lines[0] ?? '';",
    "array-space": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/) : []; output = values.join(' ');",
    "array-comma": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/) : []; output = values.join(',');",
    "array-lines": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/) : []; output = values.join('\\n');",
    "array-length": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/) : []; output = `${values.length}\\n${values.join(' ')}`;",
    "array-reverse": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/) : []; output = values.reverse().join(' ');",
    "matrix-rows": "const [n] = (lines[0] ?? '0').trim().split(/\\s+/).map(Number); output = lines.slice(1, n + 1).map(line => line.trim().split(/\\s+/).join(' ')).join('\\n');",
    "chars-compact": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/) : []; output = values.join('');",
    "array-empty": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/) : []; output = values.length ? values.join(' ') : 'EMPTY';",
    "array-bigint": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/).map(value => BigInt(value).toString()) : []; output = values.join(' ');",
    "array-float": "const values = lines[1]?.trim() ? lines[1].trim().split(/\\s+/).map(value => fixedDecimal(value, 2)) : []; output = values.join(' ');",
    "group-lines": "const t = Number(lines[0] ?? 0); output = lines.slice(1, t + 1).map(line => line.trim().split(/\\s+/).filter(Boolean).reduce((sum, value) => sum + Number(value), 0)).join('\\n');",
    "case-hash": "const t = Number(lines[0] ?? 0); output = lines.slice(1, t + 1).map((line, i) => `Case #${i + 1}: ${line.trim().split(/\\s+/).filter(Boolean).reduce((sum, value) => sum + Number(value), 0)}`).join('\\n');",
    "case-plain": "const t = Number(lines[0] ?? 0); output = lines.slice(1, t + 1).map((line, i) => `Case ${i + 1}: ${line.trim().split(/\\s+/).filter(Boolean).reduce((sum, value) => sum + Number(value), 0)}`).join('\\n');",
    "group-blank": "const t = Number(lines[0] ?? 0); output = lines.slice(1, t + 1).map(line => line.trim().split(/\\s+/).filter(Boolean).reduce((sum, value) => sum + Number(value), 0)).join('\\n\\n');",
    "group-multiline": "const t = Number(lines[0] ?? 0); output = lines.slice(1, t + 1).flatMap(line => { const values = line.trim().split(/\\s+/).filter(Boolean).map(Number); return [String(values.reduce((a, b) => a + b, 0)), String(values.length)]; }).join('\\n');",
    "group-title": "const t = Number(lines[0] ?? 0); output = lines.slice(1, t + 1).flatMap((line, i) => [`Group ${i + 1}`, String(line.trim().split(/\\s+/).filter(Boolean).reduce((sum, value) => sum + Number(value), 0))]).join('\\n');",
    "group-no-tail-blank": "const t = Number(lines[0] ?? 0); output = lines.slice(1, t + 1).map(line => line.trim().split(/\\s+/).filter(Boolean).reduce((sum, value) => sum + Number(value), 0)).join('\\n\\n');",
    "group-buffer": "const t = Number(lines[0] ?? 0); const out = []; for (let i = 0; i < t; i += 1) out.push(String(Number(lines[i + 1] ?? 0) * 2)); output = out.join('\\n');",
    "fixed-two": "output = fixedDecimal(tokens[0] ?? '0', 2);",
    "fixed-n": "output = fixedDecimal(tokens[0] ?? '0', Number(tokens[1] ?? 0));",
    "percentage": "output = `${(Number(tokens[0] ?? 0) * 100).toFixed(2)}%`;",
    "scientific": "output = Number(tokens[0] ?? 0).toExponential(3);",
    "leading-zero": "const numberText = tokens[0] ?? '0'; const width = Number(tokens[1] ?? 0); const sign = numberText.startsWith('-') ? '-' : ''; output = sign + numberText.replace(/^[+-]/, '').padStart(Math.max(0, width - sign.length), '0');",
    "plus-sign": "const value = BigInt(tokens[0] ?? '0'); output = value > 0n ? `+${value}` : value.toString();",
    "round-two": "output = fixedDecimal(tokens[0] ?? '0', 2);",
    "safe-sum": "output = addDecimalsFixed(tokens[0] ?? '0', tokens[1] ?? '0', 2);",
    "negative-zero": "const value = Number(tokens[0] ?? 0); output = Object.is(value, -0) || Math.abs(value) < 0.0005 ? '0.00' : value.toFixed(2);",
    "right-align": "const width = Number(tokens[0] ?? 0); output = tokens.slice(1).join(' ').padStart(width, ' ');",
    "left-align": "const width = Number(tokens[0] ?? 0); output = `${tokens.slice(1).join(' ').padEnd(width, ' ')}|`;",
    "simple-table": "const n = Number(lines[0] ?? 0); output = lines.slice(1, n + 1).map(line => { const [name, score] = line.trim().split(/\\s+/); return `${name.padEnd(10, ' ')}${score.padStart(5, ' ')}`; }).join('\\n');",
    "matrix-align": "const [n] = (lines[0] ?? '0').trim().split(/\\s+/).map(Number); const rows = lines.slice(1, n + 1).map(line => line.trim().split(/\\s+/)); const width = Math.max(1, ...rows.flat().map(value => value.length)); output = rows.map(row => row.map(value => value.padStart(width, ' ')).join(' ')).join('\\n');",
    "header-line": "const header = lines[0] ?? ''; output = `${header}\\n${'-'.repeat(Array.from(header).length)}`;",
    "strings-align": "const n = Number(lines[0] ?? 0); const values = lines.slice(1, n + 1); const width = Math.max(0, ...values.map(value => Array.from(value).length)); output = values.map(value => `${value}${' '.repeat(width - Array.from(value).length)}: ${Array.from(value).length}`).join('\\n');",
    "unicode-width": "const n = Number(lines[0] ?? 0); output = lines.slice(1, n + 1).map(value => `codePoints:${Array.from(value).length}:${value}`).join('\\n');",
    "concat": "output = `${lines[0] ?? ''}-${lines[1] ?? ''}`;",
    "template": "output = `${tokens[0] ?? ''} is ${tokens[1] ?? '0'} years old.`;",
    "backslash": "output = (lines[0] ?? '').replace(/\\//g, '\\\\');",
    "quotes": "output = `\"${lines[0] ?? ''}\"`;",
    "tabs": "output = tokens.join('\\t');",
    "multiline": "output = lines.slice(0, 3).join('\\n');",
    "json": "output = JSON.stringify(JSON.parse(input || 'null'));",
    "range-lines": "const n = Number(tokens[0] ?? 0); const out = []; for (let i = 1; i <= n; i += 1) out.push(String(i)); output = out.join('\\n');",
    "squares-lines": "const n = Number(tokens[0] ?? 0); const out = []; for (let i = 1; i <= n; i += 1) out.push(String(i * i)); output = out.join('\\n');",
    "double-lines": "const n = Number(tokens[0] ?? 0); const out = []; for (let i = 1; i <= n; i += 1) out.push(String(i * 2)); output = out.join('\\n');",
    "triple-lines": "const n = Number(tokens[0] ?? 0); const out = []; for (let i = 1; i <= n; i += 1) out.push(String(i * 3)); output = out.join('\\n');",
    "indexed-lines": "const n = Number(tokens[0] ?? 0); const out = []; for (let i = 1; i <= n; i += 1) out.push(`${i}:${i % 10}`); output = out.join('\\n');",
    "bounded-lines": "const n = Number(tokens[0] ?? 0); if (n > 10000) output = 'OUTPUT_TOO_LARGE'; else { const out = []; for (let i = 1; i <= n; i += 1) out.push(String(i)); output = out.join('\\n'); }",
}

DECIMAL_HELPERS = """
function decimalParts(text) {
  const match = String(text).trim().match(/^([+-]?)(\\d+)(?:\\.(\\d*))?$/);
  if (!match) throw new Error('invalid decimal input');
  return { negative: match[1] === '-', whole: match[2], fraction: match[3] ?? '' };
}
function fixedDecimal(text, digits) {
  const parts = decimalParts(text);
  const scale = 10n ** BigInt(digits);
  const padded = parts.fraction.padEnd(digits + 1, '0');
  let units = BigInt(parts.whole) * scale + BigInt(padded.slice(0, digits) || '0');
  if (padded[digits] >= '5') units += 1n;
  const sign = parts.negative && units !== 0n ? '-' : '';
  if (digits === 0) return sign + units.toString();
  const rendered = units.toString().padStart(digits + 1, '0');
  return `${sign}${rendered.slice(0, -digits)}.${rendered.slice(-digits)}`;
}
function addDecimalsFixed(left, right, digits) {
  const a = decimalParts(left);
  const b = decimalParts(right);
  const scaleDigits = Math.max(a.fraction.length, b.fraction.length, digits + 1);
  const scale = 10n ** BigInt(scaleDigits);
  const scaled = value => {
    const magnitude = BigInt(value.whole) * scale
      + BigInt(value.fraction.padEnd(scaleDigits, '0') || '0');
    return value.negative ? -magnitude : magnitude;
  };
  const total = scaled(a) + scaled(b);
  const sign = total < 0n ? '-' : '';
  const rendered = (total < 0n ? -total : total).toString().padStart(scaleDigits + 1, '0');
  const decimal = `${sign}${rendered.slice(0, -scaleDigits)}.${rendered.slice(-scaleDigits)}`;
  return fixedDecimal(decimal, digits);
}
""".strip()


def reference_source(task: Task, runtime: str) -> str:
    if task.mode not in SOLVERS:
        raise RuntimeError(f"missing solver for {task.mode}")
    body = SOLVERS[task.mode]
    if runtime == "javascript-v8":
        prefix = (
            "const lines = [];\n"
            "for (let line = readline(); line !== undefined; line = readline()) {\n"
            "  lines.push(line);\n"
            "}\n"
        )
        suffix = "\nprint(String(output));\n"
    else:
        prefix = (
            "'use strict';\n"
            "const fs = require('fs');\n"
            "const raw = fs.readFileSync(0, 'utf8').replace(/\\r\\n?/g, '\\n');\n"
            "const lines = raw.split('\\n');\n"
            "if (lines.length && lines[lines.length - 1] === '') lines.pop();\n"
        )
        suffix = "\nprocess.stdout.write(`${String(output)}\\n`);\n"
    return (
        prefix
        + "const input = lines.join('\\n');\n"
        + "const tokens = input.trim() === '' ? [] : input.trim().split(/\\s+/);\n"
        + DECIMAL_HELPERS
        + "\n"
        + "let output = '';\n"
        + body
        + suffix
    )


def run_node_reference(path: Path, stdin: str, timeout: float = 10) -> str:
    result = subprocess.run(
        ["node", str(path)],
        input=stdin.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Node.js reference failed for {path.parent.name}")
    return result.stdout.decode("utf-8")


def visible(value: str) -> str:
    rendered = value.replace(" ", "␠").replace("\t", "⇥").replace("\n", "↵\n")
    return rendered if rendered else "（空字符串）"


def starter_code(task: Task, runtime: str) -> str:
    if runtime == "javascript-v8":
        return (
            "const lines = [];\n"
            "for (let line = readline(); line !== undefined; line = readline()) {\n"
            "  lines.push(line);\n"
            "}\n\n"
            f"// TODO: {task.title}\n"
            "const output = '';\n"
            "print(output);\n"
        )
    return (
        "const fs = require('fs');\n\n"
        "const input = fs.readFileSync(0, 'utf8');\n\n"
        f"// TODO: {task.title}\n"
        "const output = '';\n"
        "process.stdout.write(`${output}\\n`);\n"
    )


def input_description(family: str) -> str:
    if family in {"array", "float-array"}:
        return "第一行是数组长度 n，第二行包含 n 个元素；n=0 时第二行为空。"
    if family == "matrix":
        return "第一行给出 n 和 m，随后 n 行每行包含 m 个字段。"
    if family in {"groups", "many-groups"}:
        return "第一行给出测试组数 T，随后每行是一组待格式化的简单数据。"
    if family == "count":
        return "输入一个非负整数 n，表示需要产生的结果数量。"
    if family in {"records", "string-list"}:
        return "第一行给出记录数量 n，随后 n 行给出记录正文。"
    if family == "ignored":
        return "输入内容不参与结果，可能为空。"
    return "输入为一行或少量多行 UTF-8 文本，字段含义见题目描述与公开样例。"


def write_problem(task: Task, chapter_order: int, prerequisite: str | None) -> Path:
    inputs = cases_for(task.family)
    reference_directory = REFERENCE_ROOT / task.slug
    reference_directory.mkdir(parents=True, exist_ok=True)
    v8_path = reference_directory / "solution-v8.js"
    node_path = reference_directory / "solution-nodejs.js"
    write_utf8(v8_path, reference_source(task, "javascript-v8"))
    write_utf8(node_path, reference_source(task, "nodejs"))
    outputs = [run_node_reference(node_path, stdin, timeout=20) for stdin in inputs]

    test_directory = TEST_ROOT / task.slug
    test_directory.mkdir(parents=True, exist_ok=True)
    hidden_cases = []
    for index, ((scenario, label), stdin, stdout, score) in enumerate(
        zip(SCENARIOS, inputs[2:], outputs[2:], SCORES), 1
    ):
        input_path = test_directory / f"{index:02d}.in"
        output_path = test_directory / f"{index:02d}.out"
        input_path.write_bytes(stdin.encode("utf-8"))
        output_path.write_bytes(stdout.encode("utf-8"))
        checksum = hashlib.sha256(stdin.encode() + b"\0" + stdout.encode()).hexdigest()
        hidden_cases.append(
            {
                "sequence": index,
                "score": score,
                "scenario": scenario,
                "scenario_description": f"{label}：检查“{task.title}”的 stdout 字节结构。",
                "input_file": f"js-acm-output/{task.slug}/{index:02d}.in",
                "output_file": f"js-acm-output/{task.slug}/{index:02d}.out",
                "checksum": checksum,
            }
        )

    samples = [
        {
            "input": stdin,
            "output": stdout,
            "explanation": f"输出可视化为 `{visible(stdout)}`。↵ 表示换行，␠ 表示空格，⇥ 表示 TAB。",
        }
        for stdin, stdout in zip(inputs[:2], outputs[:2])
    ]
    wrong_visible = visible("debug: " + outputs[0])
    description = (
        f"本练习专门训练 **{task.title}**，计算本身保持简单，重点是 stdout 格式。\n\n"
        "### 正确示例\n\n"
        f"使用可见空白符表示为：`{visible(outputs[0])}`。\n\n"
        "### 常见错误示例\n\n"
        f"`{wrong_visible}` 会因为包含额外调试前缀而得到 Wrong Answer。\n\n"
        "### exact checker 规则\n\n"
        "CRLF 与 LF 等价；每行行尾空格和最终空白会被忽略。行内多余空格、内部空行、"
        "TAB/空格混用和额外调试行仍会被识别。缺少最后一个换行符可以通过。"
    )
    common_errors = [
        "输出 result:、debug 等题目未要求的提示语。",
        "把一个空格写成多个空格，或把换行写成空格。",
        "在循环中逐次 console.log，造成大量系统调用和不合理超时。",
        "直接调试打印 BigInt，出现不符合题意的 n 后缀。",
        "混淆 TAB、反斜杠、引号等转义后的实际输出。",
    ]
    document = {
        "slug": task.slug,
        "title": task.title,
        "description": description,
        "difficulty": "hard" if task.chapter == "js-acm-output-performance" else "medium" if task.chapter in {"js-acm-output-groups", "js-acm-output-numbers", "js-acm-output-alignment"} else "easy",
        "training_category": "output-format",
        "tags": ["stdout", "output-format", "javascript-v8", "nodejs"],
        "input_description": input_description(task.family),
        "output_description": "精确输出要求：" + task.exact_rule,
        "data_constraints": "输入为 UTF-8 文本；单个隐藏输入不超过 2 MB；单次标准输出必须低于平台 1 MB 上限。",
        "sample_input": samples[0]["input"],
        "sample_output": samples[0]["output"],
        "sample_explanation": samples[0]["explanation"],
        "samples": samples,
        "learning_objective": task.objective,
        "v8_hint": "把所有结果先放入数组，使用 join 组成字符串后只调用一次 print(output)。print 会自动追加最终换行。",
        "nodejs_hint": "少量结果可用 console.log；批量结果优先数组加 join，最后调用一次 process.stdout.write。",
        "common_errors": common_errors,
        "chapter": task.chapter,
        "chapter_order": chapter_order,
        "prerequisites": [prerequisite] if prerequisite else [],
        "estimated_minutes": task.minutes,
        "starter_code_v8": starter_code(task, "javascript-v8"),
        "starter_code_nodejs": starter_code(task, "nodejs"),
        "time_limit_ms": 5000 if task.chapter == "js-acm-output-performance" else 1000,
        "memory_limit_mb": 256,
        "source": "CodeArena JavaScript ACM 原创输出课程",
        "publish": True,
        "reference_solutions": {
            "javascript_v8": f"reference-solutions/js-acm-output/{task.slug}/solution-v8.js",
            "nodejs": f"reference-solutions/js-acm-output/{task.slug}/solution-nodejs.js",
        },
        "test_set": {"version": 1, "checker_type": "exact", "cases": hidden_cases},
    }
    problem_path = PROBLEM_ROOT / f"{task.slug}.yaml"
    problem_path.parent.mkdir(parents=True, exist_ok=True)
    write_utf8(
        problem_path,
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=100),
    )
    return problem_path


def update_catalog(tasks: list[Task], paths: list[Path]) -> None:
    manifest_path = ROOT / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    existing = [item for item in manifest["problems"] if not item.startswith("problems/js-acm-output/")]
    manifest["problems"] = existing + [path.relative_to(ROOT).as_posix() for path in paths]
    write_utf8(manifest_path, yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))

    tags_path = ROOT / "tags.yaml"
    tags = yaml.safe_load(tags_path.read_text(encoding="utf-8"))
    tags["tags"] = [item for item in tags["tags"] if item["slug"] != "output-format"]
    tags["tags"].append({"slug": "output-format", "name": "常见输出格式"})
    write_utf8(tags_path, yaml.safe_dump(tags, allow_unicode=True, sort_keys=False))

    collections_path = ROOT / "collections.yaml"
    collections = yaml.safe_load(collections_path.read_text(encoding="utf-8"))
    output_chapters = {chapter.slug for chapter in CHAPTERS}
    collections["collections"] = [
        item for item in collections["collections"] if item["slug"] not in output_chapters
    ]
    for chapter in CHAPTERS:
        collections["collections"].append(
            {
                "slug": chapter.slug,
                "title": chapter.title,
                "description": chapter.description,
                "company": "CodeArena",
                "is_public": True,
                "problems": [task.slug for task in tasks if task.chapter == chapter.slug],
            }
        )
    write_utf8(
        collections_path,
        yaml.safe_dump(collections, allow_unicode=True, sort_keys=False),
    )


def main() -> int:
    tasks = build_tasks()
    if len(tasks) != 63 or len({task.slug for task in tasks}) != 63:
        raise RuntimeError("output course must contain exactly 63 unique exercises")
    paths: list[Path] = []
    previous: str | None = None
    for chapter in CHAPTERS:
        chapter_tasks = [task for task in tasks if task.chapter == chapter.slug]
        for order, task in enumerate(chapter_tasks, 1):
            paths.append(write_problem(task, order, previous))
            previous = task.slug
    update_catalog(tasks, paths)
    print(json.dumps({
        "status": "success",
        "chapters": len(CHAPTERS),
        "problems": len(tasks),
        "public_samples": len(tasks) * 2,
        "hidden_cases": len(tasks) * 6,
        "reference_solutions": len(tasks) * 2,
    }, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

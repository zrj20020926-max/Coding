from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ChapterSpec:
    slug: str
    title: str
    description: str
    source_collection: str
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class CourseSpec:
    slug: str
    title: str
    description: str
    type: str
    chapters: tuple[ChapterSpec, ...]


def chapter(
    slug: str,
    title: str,
    description: str,
    source: str,
    start: int | None = None,
    end: int | None = None,
) -> ChapterSpec:
    return ChapterSpec(slug, title, description, source, start, end)


COURSES = (
    CourseSpec(
        "javascript-v8-quickstart",
        "JavaScript V8 快速入门",
        "掌握 readline()、print() 与 V8 兼容模式的 EOF 语义。",
        "input",
        (chapter("v8-readline-print", "readline 与 print", "从最小输入开始熟悉 V8 ACM 运行时。", "js-acm-single-value", 0, 4),),
    ),
    CourseSpec(
        "nodejs-stdin-quickstart",
        "Node.js stdin 快速入门",
        "掌握 fs.readFileSync(0, 'utf8') 与标准输出缓冲。",
        "input",
        (chapter("nodejs-stdin-basics", "stdin 原始文本", "练习空白、BigInt 与空输入的 Node.js 处理方式。", "js-acm-single-value", 4, 8),),
    ),
    CourseSpec(
        "single-value-and-line-input",
        "单值和单行输入",
        "系统训练一行内定长、变长和混合分隔字段。",
        "input",
        (chapter("single-line-tokenization", "单行拆分与转换", "正确处理空格、TAB 和自定义分隔符。", "js-acm-single-line-values"),),
    ),
    CourseSpec(
        "multi-line-input",
        "多行输入",
        "使用行数组或游标读取固定与变长多行结构。",
        "input",
        (chapter("multi-line-cursor", "多行游标", "处理固定行数、空行、CRLF 与原始空格。", "js-acm-multi-line"),),
    ),
    CourseSpec(
        "test-case-groups",
        "T 组测试",
        "掌握组数、组内变长记录和 Case 输出格式。",
        "mixed",
        (chapter("test-case-parsing", "测试组解析", "从固定结构逐步过渡到大量变长测试组。", "js-acm-test-cases"),),
    ),
    CourseSpec(
        "eof-and-sentinel",
        "EOF 与哨兵",
        "区分文件结束、空行和业务哨兵，避免丢失最后一组数据。",
        "input",
        (
            chapter("read-until-eof", "读取到 EOF", "使用安全游标持续读取完整数据流。", "js-acm-read-until-eof"),
            chapter("sentinel-termination", "哨兵结束", "正确停止且不把哨兵计入输出。", "js-acm-sentinel"),
        ),
    ),
    CourseSpec(
        "arrays-and-matrices",
        "数组和矩阵",
        "组织一维、二维、规则和不规则数值输入。",
        "input",
        (
            chapter("array-input-structures", "数组输入", "处理定长、变长、BigInt 和空数组。", "js-acm-arrays"),
            chapter("matrix-input-structures", "矩阵输入", "处理字符网格、矩阵尾字段和多组矩阵。", "js-acm-matrices"),
        ),
    ),
    CourseSpec(
        "strings-and-empty-lines",
        "字符串与空行",
        "保留字符串原始结构并理解 Unicode 字符与字节差异。",
        "input",
        (chapter("string-input-details", "字符串细节", "覆盖空字符串、Unicode、JSON 文本和多行内容。", "js-acm-strings"),),
    ),
    CourseSpec(
        "mixed-formats",
        "混合格式",
        "解析记录、图、区间与命令流等嵌套格式。",
        "mixed",
        (chapter("mixed-records", "混合记录", "组合字符串、数字、数组和矩阵字段。", "js-acm-mixed-nested", 0, 8),),
    ),
    CourseSpec(
        "stdout-formats",
        "输出格式",
        "精确控制 stdout 的空格、换行、精度、拼接与对齐。",
        "output",
        (
            chapter("stdout-basics", "基础输出", "训练单值、固定文本和末尾换行。", "js-acm-output-basics"),
            chapter("stdout-arrays", "数组输出", "训练数组连接、逐行输出和二维结构。", "js-acm-output-arrays"),
            chapter("stdout-groups", "多组结果", "训练 Case 格式、多行结果和组间空行。", "js-acm-output-groups"),
            chapter("stdout-numbers", "数值格式", "训练小数、百分比、科学计数法和 BigInt。", "js-acm-output-numbers"),
            chapter("stdout-alignment", "表格与对齐", "训练固定宽度、补零和 Unicode 对齐边界。", "js-acm-output-alignment"),
            chapter("stdout-strings", "字符串格式", "训练转义、多行文本、Unicode 与调试输出约束。", "js-acm-output-strings"),
        ),
    ),
    CourseSpec(
        "large-input-performance",
        "大输入与高性能解析",
        "使用索引游标和批量输出处理高数据量，避免重复 split/shift。",
        "performance",
        (
            chapter("large-input-parsing", "高性能输入", "覆盖十万整数、百万 token 与大字符串。", "js-acm-large-input"),
            chapter("large-output-buffering", "高性能输出", "缓冲结果并控制输出大小与内存。", "js-acm-output-performance"),
        ),
    ),
    CourseSpec(
        "comprehensive-io-training",
        "综合训练",
        "综合运用不同字段类型与完整解析模板。",
        "mixed",
        (chapter("comprehensive-records", "综合记录", "完成不同类型字段和完整推荐模式练习。", "js-acm-mixed-nested", 8, None),),
    ),
)


def main() -> int:
    collections = yaml.safe_load((ROOT / "collections.yaml").read_text(encoding="utf-8"))
    collection_map = {item["slug"]: item["problems"] for item in collections["collections"]}
    manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text(encoding="utf-8"))
    problem_documents = {}
    for relative in manifest["problems"]:
        document = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
        problem_documents[document["slug"]] = document

    rendered = []
    seen: set[str] = set()
    for course_order, course in enumerate(COURSES, start=1):
        chapters = []
        for chapter_order, item in enumerate(course.chapters, start=1):
            slugs = collection_map[item.source_collection][item.start:item.end]
            if not slugs or seen.intersection(slugs):
                raise RuntimeError(f"invalid or duplicated course chapter: {item.slug}")
            seen.update(slugs)
            estimated = sum(problem_documents[slug]["estimated_minutes"] for slug in slugs)
            chapters.append(
                {
                    "slug": item.slug,
                    "title": item.title,
                    "description": item.description,
                    "sort_order": chapter_order,
                    "estimated_minutes": estimated,
                    "is_public": True,
                    "problems": slugs,
                }
            )
        rendered.append(
            {
                "slug": course.slug,
                "title": course.title,
                "description": course.description,
                "type": course.type,
                "sort_order": course_order,
                "is_public": True,
                "chapters": chapters,
            }
        )
    if seen != set(problem_documents):
        raise RuntimeError("learning courses must cover every manifest problem exactly once")
    (ROOT / "courses.yaml").write_text(
        yaml.safe_dump({"courses": rendered}, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(json.dumps({"status": "success", "courses": len(rendered), "chapters": sum(len(item["chapters"]) for item in rendered), "exercises": len(seen)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

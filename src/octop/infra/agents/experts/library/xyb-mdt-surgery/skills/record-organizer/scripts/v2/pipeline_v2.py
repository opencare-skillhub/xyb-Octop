"""
v2 端到端流水线

流程：
  原始 .md -> 脱敏 -> Map LLM -> Shuffle -> Reduce LLM -> Profile -> 报告
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根在 sys.path 中（支持直接 python scripts/v2/pipeline_v2.py 运行）
_ProjectRoot = Path(__file__).resolve().parent.parent.parent
if str(_ProjectRoot) not in sys.path:
    sys.path.insert(0, str(_ProjectRoot))

# 自动加载 .env（如果存在）
_dotenv_path = _ProjectRoot / ".env"
if _dotenv_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_dotenv_path), override=True)
    except ImportError:
        pass  # python-dotenv 未安装时静默跳过

logger = logging.getLogger(__name__)

from scripts.v2.desensitize import desensitize_directory
from scripts.v2.map_extract import extract_batch
from scripts.v2.reduce_merge import reduce_lab_trends, reduce_imaging_narrative, reduce_medication_history
from scripts.mdt_analysis import run_mdt_analysis
from scripts.v2.shuffle_group import group_by_type, merge_lab_trends

try:
    from jinja2 import Environment, FileSystemLoader, Template
    _JINJA2_AVAILABLE = True
except ImportError:
    _JINJA2_AVAILABLE = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_key(file_path: Path) -> str:
    """统一用 resolve() 后的路径作为增量比对的 key（C7）。"""
    return str(Path(file_path).resolve())


def _load_existing_mappings(mappings_path: Path) -> Dict[str, Any]:
    """从 mappings.json 恢复已有映射（C6 增量合并）。"""
    if not mappings_path.exists():
        return {}
    try:
        return json.loads(mappings_path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _persist_mappings(
    mappings: Dict[str, Any],
    mappings_path: Path,
    existing: Dict[str, Any],
) -> None:
    """增量合并并持久化脱敏映射（C6）。"""
    merged = dict(existing)
    merged.update(mappings)
    mappings_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8'
    )


# 需要 OCR 预处理的原始文件扩展名（对齐 route_ocr.RAW_OCR_EXTENSIONS）
# 文本/数据类文件（.md/.txt/.json/.csv）不送 OCR，直接进 v2 流程
_NON_OCR_EXTENSIONS = {'.md', '.txt', '.json', '.csv'}

# MinerU / 云端 OCR 不支持的图片格式 → 预处理阶段统一转码为 JPEG
_HEIC_EXTENSIONS = {'.heic', '.heif'}


def _normalize_heic_files(raw_files: List[Path], work_dir: Path) -> List[Path]:
    """把 HEIC/HEIF 转码为 JPEG（保留 stem，便于下游 md 命名一致）。

    优先用 pillow_heif，其次回退 macOS 内置 sips。转码失败则保留原文件
    （交由下游 OCR 引擎自行处理或标记失败），不中断流程。
    """
    heic = [f for f in raw_files if f.suffix.lower() in _HEIC_EXTENSIONS]
    if not heic:
        return raw_files

    conv_dir = work_dir / '_converted'
    conv_dir.mkdir(parents=True, exist_ok=True)
    mapping: Dict[Path, Path] = {}

    for f in heic:
        out = conv_dir / f"{f.stem}.jpg"
        if out.exists() and out.stat().st_size > 0:
            mapping[f] = out
            continue
        ok = _convert_heic_to_jpg(f, out)
        if ok:
            mapping[f] = out
            logger.info("HEIC 转码: %s -> %s", f.name, out.name)
        else:
            logger.warning("HEIC 转码失败，保留原文件: %s", f.name)

    return [mapping.get(f, f) for f in raw_files]


def _convert_heic_to_jpg(src: Path, dst: Path) -> bool:
    """HEIC→JPEG，返回是否成功。pillow_heif 优先，回退 macOS sips。"""
    # 方案 A：pillow_heif + PIL
    try:
        import pillow_heif  # type: ignore
        from PIL import Image  # type: ignore
        pillow_heif.register_heif_opener()
        with Image.open(str(src)) as im:
            im.convert('RGB').save(str(dst), 'JPEG', quality=92)
        return dst.exists() and dst.stat().st_size > 0
    except Exception:
        pass
    # 方案 B：macOS 内置 sips
    try:
        import subprocess
        res = subprocess.run(
            ['sips', '-s', 'format', 'jpeg', str(src), '--out', str(dst)],
            capture_output=True, timeout=60,
        )
        return res.returncode == 0 and dst.exists() and dst.stat().st_size > 0
    except Exception:
        return False


def _preprocess_raw_files(input_path: Path, output_path: Path, *, skip_ocr: bool = False) -> Path:
    """检测原始图片/PDF，做 OCR 预处理 → 写入 output/extracted/*.md，返回 md 输入目录。

    若无原始文件直接返回 input_path；skip_ocr 或 OCR 失败也写入空 md 不中断。
    """
    raw_files = [
        f for f in input_path.iterdir()
        if f.is_file()
        and f.suffix.lower() not in _NON_OCR_EXTENSIONS
        and not f.name.startswith('.')
    ]

    if not raw_files:
        return input_path

    logger.info("检测到 %d 个原始文件，开始 OCR 预处理", len(raw_files))
    extract_dir = output_path / 'extracted'
    extract_dir.mkdir(parents=True, exist_ok=True)

    # HEIC/HEIF 转码为 JPEG（MinerU/云端 OCR 不支持 HEIC，否则会整批失败）
    raw_files = _normalize_heic_files(raw_files, extract_dir)

    # 已有的 .md/.txt 等文本文件直接软链/复制到 extract_dir，统一输入目录
    import shutil
    for f in input_path.iterdir():
        if f.is_file() and f.suffix.lower() in _NON_OCR_EXTENSIONS and not f.name.startswith('.'):
            dst = extract_dir / f.name
            if not dst.exists():
                try:
                    shutil.copy2(f, dst)
                except Exception:
                    dst.write_text(f.read_text(encoding='utf-8'), encoding='utf-8')

    if skip_ocr:
        for raw_file in raw_files:
            (extract_dir / f"{raw_file.stem}.md").write_text('', encoding='utf-8')
        return extract_dir

    from scripts.route_ocr import extract_text, extract_via_mineru_batch, extract_via_mineru, route_ocr

    # 第一步：路由所有文件，区分 mineru 和非 mineru
    mineru_files: List[Path] = []
    other_files: List[Path] = []
    for raw_file in raw_files:
        try:
            engine = route_ocr(raw_file)
        except Exception:
            engine = 'mineru'  # 路由失败默认走 mineru
        if engine == 'mineru':
            mineru_files.append(raw_file)
        else:
            other_files.append(raw_file)

    # 第二步：智能选择 single vs batch mineru
    #   - PDF 页数 >10 → batch（大文件值得统一轮询）
    #   - 文件数 >50 → batch（分批并行上传，避免逐个轮询超时）
    #   - 否则 → single（少量小文件，直接调更快，少开销，带重试）
    BIG_PDF_THRESHOLD = 10
    BATCH_COUNT_THRESHOLD = 50
    try:
        import fitz  # PyMuPDF 判断 PDF 页数
    except ImportError:
        fitz = None

    has_big_pdf = False
    for f in mineru_files:
        if fitz and f.suffix.lower() == '.pdf':
            try:
                doc = fitz.open(str(f))
                if doc.page_count > BIG_PDF_THRESHOLD:
                    has_big_pdf = True
                doc.close()
            except Exception:
                pass

    use_batch = has_big_pdf or len(mineru_files) > BATCH_COUNT_THRESHOLD

    if use_batch:
        batch_files = mineru_files
        single_files = []
    else:
        batch_files = []
        single_files = mineru_files

    # 第三步：处理单文件 mineru（带重试，fast path）
    for raw_file in single_files:
        logger.info("处理原始文件(MinerU single): %s", raw_file.name)
        md_path = extract_dir / f"{raw_file.stem}.md"
        text = extract_via_mineru(raw_file, extract_dir=extract_dir)
        md_path.write_text(text if text else '', encoding='utf-8')
        logger.info("OCR 完成: %s -> %s (%d 字符)", raw_file.name, md_path.name, len(text or ''))

    # 第四步：批量处理 mineru 文件（一次 API 调用 ≤50 文件）
    if batch_files:
        logger.info("MinerU 批量处理 %d 个文件（含大PDF/多文件场景）...", len(batch_files))
        batch_results = extract_via_mineru_batch(
            batch_files,
            extract_dir=extract_dir,
        )
        for raw_file in batch_files:
            md_path = extract_dir / f"{raw_file.stem}.md"
            text = batch_results.get(raw_file, '')
            md_path.write_text(text if text else '', encoding='utf-8')
            logger.info("OCR 完成: %s -> %s (%d 字符)", raw_file.name, md_path.name, len(text or ''))

    # 第五步：处理非 mineru 文件（逐文件，local_pdf 等）
    for raw_file in other_files:
        logger.info("处理原始文件(%s): %s", route_ocr(raw_file), raw_file.name)
        md_path = extract_dir / f"{raw_file.stem}.md"
        try:
            text = extract_text(raw_file, extract_dir=extract_dir)
            md_path.write_text(text if text else '', encoding='utf-8')
            logger.info("OCR 完成: %s -> %s (%d 字符)", raw_file.name, md_path.name, len(text or ''))
        except Exception as exc:
            logger.warning("OCR 失败 %s: %s", raw_file.name, exc)
            md_path.write_text('', encoding='utf-8')

    # 第六步：OCR 文本预清洗（T2 / 根因 R3、R13）
    #   仅在派生目录 extract_dir 上操作，绝不修改用户原始输入。
    _clean_extracted_dir(extract_dir)

    return extract_dir


def _clean_extracted_dir(extract_dir: Path) -> None:
    """对 extracted/*.md 做 OCR 噪声清洗（云链接/安全码/界面文字/对话口水/页码）。

    基因检测报告跳过清洗（数值/表格密集且无对话噪声，清洗可能误删有效内容）。
    """
    try:
        from scripts.v2.clean_ocr import clean as _clean_ocr
        from scripts.v2.segment import is_genetic_report
    except ImportError:
        return
    for md_path in extract_dir.glob('*.md'):
        try:
            raw = md_path.read_text(encoding='utf-8')
        except Exception:
            continue
        if not raw:
            continue
        if is_genetic_report(raw):
            logger.info("OCR 清洗跳过(基因检测报告): %s", md_path.name)
            continue
        cleaned = _clean_ocr(raw)
        if cleaned != raw:
            md_path.write_text(cleaned, encoding='utf-8')
            logger.info("OCR 清洗: %s (%d -> %d 字符)", md_path.name, len(raw), len(cleaned))


def run_pipeline(
    input_dir: str,
    output_dir: str,
    *,
    patient_id: str = 'P_report_mess',
    model: Optional[str] = None,
    skip_ocr: bool = False,
    formats: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """执行 v2 MapReduce 流水线。

    支持原始图片/PDF 输入（自动 OCR 预处理 → extracted/*.md）；
    也支持直接 .md 输入。skip_ocr=True 跳过 OCR（仅处理 .md）。

    formats: 输出格式列表，['html', 'md', 'docx', 'xlsx'] 的子集，
             None（默认）表示生成所有格式。
    """
    input_path = Path(input_dir).resolve()  # C7: resolve 入参
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Phase 0: 原始文件 OCR 预处理（若有）
    md_input_dir = _preprocess_raw_files(input_path, output_path, skip_ocr=skip_ocr)

    md_files = sorted(md_input_dir.glob('*.md'))
    if not md_files:
        return {'patient_id': patient_id, 'status': 'no_input', 'files': 0}

    # Phase 1: 脱敏
    sanitized_dir = output_path / 'sanitized'
    mappings_path = output_path / 'mappings.json'
    existing_mappings = _load_existing_mappings(mappings_path)  # C6: 恢复映射
    mappings = desensitize_directory(str(md_input_dir), str(sanitized_dir))
    _persist_mappings(mappings, mappings_path, existing_mappings)  # C6: 持久化

    # Phase 1.5: 复合文档切分（T1 / 根因 R1）
    #   把同时含 检验/基因/病理/影像/用药 的复合文档原地切成多个逻辑子文档，
    #   每段独立分类与抽取。在 sanitized_dir 原地操作，渲染层的原文兜底仍可命中。
    try:
        from scripts.v2.segment import segment_directory
        seg_counts = segment_directory(str(sanitized_dir), str(sanitized_dir))
        _split = {k: v for k, v in seg_counts.items() if v > 1}
        if _split:
            logger.info('复合文档切分: %s', ', '.join(f'{k}->{v}段' for k, v in _split.items()))
    except Exception as exc:
        logger.warning('复合文档切分失败（降级为整篇抽取）: %s', exc)

    # Phase 2: Map
    map_dir = output_path / 'map'
    extracted = extract_batch(str(sanitized_dir), str(map_dir), model=model)

    # T9: Map 输出契约校验（非致命，仅告警）
    try:
        from scripts.v2.validate import validate_map_output
        _issue_count = 0
        for _it in extracted:
            for _iss in validate_map_output(_it):
                logger.warning('Map 契约告警 [%s]: %s', _it.get('_source_file', ''), _iss)
                _issue_count += 1
        if _issue_count:
            logger.warning('Map 契约校验共 %d 条告警', _issue_count)
    except Exception as _exc:
        logger.debug('Map 契约校验跳过: %s', _exc)

    # Phase 3: Shuffle
    groups = group_by_type(extracted)
    lab_trends = merge_lab_trends(groups.get('lab', []) + groups.get('clinical', []))

    # Phase 4: Reduce
    lab_analysis = reduce_lab_trends(lab_trends, model=model)
    med_timeline = reduce_medication_history(groups.get('medication', []), model=model)
    imaging_narrative = reduce_imaging_narrative(groups.get('imaging', []), model=model)

    # Phase 4.5: MDT 多学科分析
    mdt_analysis = run_mdt_analysis(
        {
            'demographics': {},
            'lab_trends': lab_trends,
            'lab_analysis': lab_analysis,
            'medication_timeline': med_timeline,
            'imaging_narrative': imaging_narrative,
            'gaps': [],
            'timeline': [],
        },
        groups,
        model=model,
    )

    # MDT 结果单独落盘（HTML/MD/DOCX 渲染层与未来导出均可复用）
    try:
        (output_path / 'mdt_analysis.json').write_text(
            json.dumps(mdt_analysis, ensure_ascii=False, indent=2), encoding='utf-8'
        )
    except Exception as exc:
        logger.warning('mdt_analysis.json 落盘失败：%s', exc)

    # Phase 5: Profile 组装
    profile: Dict[str, Any] = {
        'patient_id': patient_id,
        'generated_at': _now_iso(),
        'input_dir': str(input_path),
        'file_count': len(md_files),
        'map_count': len(extracted),
        'groups': {k: len(v) for k, v in groups.items()},
        'lab_trends': lab_trends,
        'lab_analysis': lab_analysis,
        'medication_timeline': med_timeline,
        'imaging_narrative': imaging_narrative,
        'mdt_analysis': mdt_analysis,
        'mappings_path': str(mappings_path),
        'output_dir': str(output_path),
    }

    (output_path / 'profile.json').write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    # Phase 6: 渲染报告
    _render_reports(profile, groups, output_path, formats=formats)

    logger.info(
        'v2 流水线完成: patient=%s files=%d groups=%s',
        patient_id,
        len(extracted),
        ','.join(f'{k}={len(v)}' for k, v in groups.items()),
    )
    return profile


def _render_reports(
    profile: Dict[str, Any],
    groups: Dict[str, List[Dict[str, Any]]],
    output_path: Path,
    formats: List[str] | None = None,
) -> None:
    """生成 HTML / Markdown / DOCX / XLSX 报告。

    formats: ['html', 'md', 'docx', 'xlsx'] 的子集，None 表示生成所有。
    """
    from scripts.v2.render_html import render_html_report
    from scripts.render_md import render_md

    if formats is None or 'html' in formats:
        html_path = render_html_report(profile, groups, output_path)
        if html_path:
            logger.info('HTML 报告已生成: %s', html_path)
        else:
            logger.warning('HTML 报告渲染失败')

    if formats is None or 'md' in formats:
        try:
            md_path = render_md(profile, groups=groups, output_path=output_path / 'case_report.md')
            logger.info('Markdown 报告已生成: %s', md_path)
        except Exception as exc:
            logger.warning('Markdown 报告渲染失败: %s', exc)

    if formats is None or 'docx' in formats:
        try:
            from scripts.v2.render_docx import render_docx_report
            docx_path = render_docx_report(profile, groups, output_path)
            if docx_path:
                logger.info('DOCX 报告已生成: %s', docx_path)
        except Exception as exc:
            logger.warning('DOCX 报告渲染失败: %s', exc)

    if formats is None or 'xlsx' in formats:
        try:
            from scripts.v2.render_xlsx import render_xlsx_report
            xlsx_path = render_xlsx_report(profile, groups, output_path)
            if xlsx_path:
                logger.info('XLSX 报告已生成: %s', xlsx_path)
        except Exception as exc:
            logger.warning('XLSX 报告渲染失败: %s', exc)


def render_only(output_dir: str, *, formats: List[str] | None = None) -> Dict[str, Any]:
    """从已有 map/*.json + profile.json 重新渲染报告，跳过 OCR/LLM。

    用于只调整渲染/结构化逻辑时快速重出报告，无需重跑昂贵的 OCR 与 LLM。
    复用已落盘的 mdt_analysis.json，避免触发 LLM 调用。
    """
    output_path = Path(output_dir)
    map_dir = output_path / 'map'
    if not map_dir.is_dir():
        raise FileNotFoundError(
            f'未找到 map 目录: {map_dir}（--render-only 需要先完整跑过一次流水线）'
        )

    extracted: List[Dict[str, Any]] = []
    for f in sorted(map_dir.glob('*.json')):
        try:
            extracted.append(json.loads(f.read_text(encoding='utf-8')))
        except Exception as exc:
            logger.warning('读取 map 失败 %s: %s', f.name, exc)
    if not extracted:
        raise FileNotFoundError(f'map 目录为空: {map_dir}')

    groups = group_by_type(extracted)

    profile_path = output_path / 'profile.json'
    profile: Dict[str, Any] = {}
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding='utf-8'))
        except Exception as exc:
            logger.warning('读取 profile.json 失败，使用空 profile: %s', exc)
    profile['output_dir'] = str(output_path)

    mdt_path = output_path / 'mdt_analysis.json'
    if mdt_path.exists():
        try:
            profile['mdt_analysis'] = json.loads(mdt_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    logger.info('重渲染：map=%d 条，分组=%s', len(extracted),
                ','.join(f'{k}={len(v)}' for k, v in groups.items()))
    # 标记离线渲染：跳过渲染期的 LLM 调用（时间轴精简/问诊建议），实现真正的 skip-LLM
    _prev = os.environ.get('RENDER_SKIP_LLM')
    os.environ['RENDER_SKIP_LLM'] = '1'
    try:
        _render_reports(profile, groups, output_path, formats=formats)
    finally:
        if _prev is None:
            os.environ.pop('RENDER_SKIP_LLM', None)
        else:
            os.environ['RENDER_SKIP_LLM'] = _prev
    logger.info('重渲染完成: %s', output_path)
    return profile


def _render_markdown(profile: Dict[str, Any], groups: Dict[str, List[Dict[str, Any]]], output_path: Path) -> None:
    """生成 Markdown 报告。"""
    lines: List[str] = []
    lines.append('# 病案整理报告')
    lines.append('')
    lines.append(f'- 患者ID：{profile.get("patient_id", "")}')
    lines.append(f'- 生成时间：{profile.get("generated_at", "")}')
    lines.append(f'- 处理文件数：{profile.get("file_count", 0)}')
    lines.append('')

    lines.append('## 分类摘要')
    lines.append('')
    for group, count in sorted((profile.get('groups') or {}).items()):
        lines.append(f'- {group}: {count}')
    lines.append('')

    lab_trends = profile.get('lab_trends') or {}
    if lab_trends:
        lines.append('## 检验指标趋势')
        lines.append('')
        for indicator, data in sorted(lab_trends.items()):
            lines.append(f'### {indicator}')
            trend = data.get('trend') or []
            if trend:
                lines.append('| 日期 | 数值 | 单位 |')
                lines.append('|------|------|------|')
                for item in trend:
                    lines.append(f'| {item.get("date", "")} | {item.get("value", "")} | {item.get("unit", "")} |')
            lines.append('')

    med_tl = profile.get('medication_timeline') or {}
    if med_tl.get('timeline'):
        lines.append('## 用药时间线')
        lines.append('')
        for med in med_tl['timeline']:
            lines.append(f'- {med.get("name", "")}: {med.get("dosage") or med.get("dose", "")} ({med.get("start_date", "")})')
        lines.append('')

    lines.append('## 免责声明')
    lines.append('')
    lines.append('本病例档案仅为医疗资料整理与结构化归档，不构成任何诊断或治疗建议。')
    lines.append('')

    output_path.write_text('\n'.join(lines), encoding='utf-8')


def _parse_format(format_arg: str) -> List[str]:
    """把 --format 字符串解析为格式列表。"""
    if format_arg == 'all':
        return ['html', 'md', 'docx', 'xlsx']
    # 别名映射
    alias = {'doc': 'docx', 'xls': 'xlsx'}
    return [alias.get(f, f) for f in format_arg.split(',')]


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    """命令行入口。"""
    import argparse
    
    parser = argparse.ArgumentParser(description='v2 病案整理流水线')
    parser.add_argument('--input-dir', help='输入目录（.md 文件 或 原始图片/PDF）；--render-only 时可省略')
    parser.add_argument('--output-dir', required=True, help='输出目录')
    parser.add_argument('--patient-id', default='P_report_mess', help='患者ID')
    parser.add_argument('--model', help='LLM 模型名称')
    parser.add_argument('--format', choices=['html', 'md', 'docx', 'xlsx', 'doc', 'xls', 'all'],
                        default='all', help='输出格式（doc/xls 是 docx/xlsx 的别名）')
    parser.add_argument('--skip-ocr', action='store_true', help='跳过 OCR 预处理（仅处理 .md 文件）')
    parser.add_argument('--render-only', action='store_true',
                        help='仅从已有 map/profile 重新渲染报告，跳过 OCR/LLM（需先完整跑过一次）')
    parser.add_argument('--open', action='store_true', help='生成后自动打开 HTML')
    parser.add_argument('--log-level', default='INFO', help='日志级别')
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    # --render-only：从已有产物重渲染，跳过 OCR/LLM
    if args.render_only:
        print("🎨 仅重渲染模式（跳过 OCR/LLM）...")
        print(f"   输出目录: {args.output_dir}")
        print(f"   输出格式: {args.format}")
        print("=" * 60)
        try:
            render_only(args.output_dir, formats=_parse_format(args.format))
        except FileNotFoundError as exc:
            print(f"❌ {exc}")
            return 1
        except Exception as exc:
            logger.exception('重渲染失败: %s', exc)
            return 1
        print("\n✅ 重渲染完成！")
        _maybe_open_html(args)
        return 0

    input_path = Path(args.input_dir) if args.input_dir else None
    if input_path is None or not input_path.exists() or not input_path.is_dir():
        print(f"❌ 输入目录不存在: {args.input_dir}（非 --render-only 模式必须提供有效 --input-dir）")
        return 1

    print(f"📋 开始运行 v2 流水线...")
    print(f"   输入目录: {input_path}")
    print(f"   输出目录: {args.output_dir}")
    print(f"   患者ID: {args.patient_id}")
    print(f"   输出格式: {args.format}")
    print("=" * 60)

    try:
        profile = run_pipeline(
            input_dir=str(input_path),
            output_dir=args.output_dir,
            patient_id=args.patient_id,
            model=args.model,
            skip_ocr=args.skip_ocr,
            formats=_parse_format(args.format),
        )
        
        print("\n" + "=" * 60)
        print("✅ v2 流水线运行完毕！")
        print(f"   患者ID: {profile.get('patient_id')}")
        print(f"   处理文件数: {profile.get('file_count', 0)}")
        print(f"   分类: {profile.get('groups', {})}")
        
        # 打开 HTML
        _maybe_open_html(args)
        
        return 0
        
    except Exception as exc:
        print(f"\n❌ 流水线运行失败: {exc}")
        import traceback
        traceback.print_exc()
        return 1


def _maybe_open_html(args) -> None:
    """按需在浏览器打开生成的 HTML 报告。"""
    if not (args.format in ('html', 'all') and getattr(args, 'open', False)):
        return
    output_path = Path(args.output_dir)
    html_file = output_path / 'report.html'
    if not html_file.exists():
        html_file = output_path / 'case_report.html'
    if html_file.exists():
        import webbrowser
        webbrowser.open(f"file://{html_file}")
        print(f"🌐 已打开报告: {html_file}")


if __name__ == '__main__':
    raise SystemExit(main())

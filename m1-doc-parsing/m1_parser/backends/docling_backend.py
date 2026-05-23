# -*- coding: utf-8 -*-
"""
Docling v2 backend adapter.

WHY: Docling is the primary engine handling all 10+ supported formats
(PDF, DOCX, XLSX, PPTX, HTML, images, CSV, Markdown). This adapter wraps
Docling's DocumentConverter behind a clean ParseResult interface so that
the converter.py pipeline can switch backends without changing its own code.

Supports:
  - Standard Pipeline (default, no VLM)
  - VLM Pipeline via picture_description (granite_docling, smoldocling, etc.)
  - Configurable OCR engines (EasyOCR, Tesseract, RapidOCR, OcrMac)
  - Batch conversion with partial-failure tolerance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ===========================================================================
# Output data model
# ===========================================================================


@dataclass
class ParseResult:
    """
    Result of a single document parse operation.

    WHY dataclass: immutable-enough for a pipeline stage output, but
    fields can be replaced downstream (e.g., quality scoring may set
    a confidence flag on the result). Also trivial to serialize for
    the CLI/Web UI.

    Fields:
        markdown: Full document text in Markdown format.
        json_dict: Full DoclingDocument as a dict (tables, figures,
            layout, reading order). None if export failed.
        page_count: Number of pages parsed (0 for non-paginated formats).
        figure_count: Number of figures/pictures extracted.
        table_count: Number of tables extracted.
    """

    markdown: str
    html: str = ""
    json_dict: dict[str, Any] | None = None
    tables_csv: str = ""
    page_count: int = 0
    figure_count: int = 0
    table_count: int = 0


# ===========================================================================
# OCR engine mapping -- maps friendly names to Docling options classes
# ===========================================================================

# WHY lazy import: OCR engines are heavy dependencies. Importing them
# at module level would break environments that only have EasyOCR installed.
# The mapping is resolved on first use inside _build_ocr_options().

_OCR_ENGINE_CLASS_MAP: dict[str, str] = {
    "easyocr": "EasyOcrOptions",
    "tesseract": "TesseractCliOcrOptions",
    "tesseract_ocr": "TesseractOcrOptions",
    "rapidocr": "RapidOcrOptions",
    "ocrmac": "OcrMacOptions",
}

# ---------------------------------------------------------------------------
# Supported VLM presets -- maps user-friendly names to vlm_model_specs attrs.
# WHY dict: lets users pass "granite_docling" and get the correct
# GRANITEDOCLING_TRANSFORMERS spec without knowing the internal naming.
# ---------------------------------------------------------------------------

_VLM_PRESET_MAP: dict[str, str] = {
    "granite_docling": "GRANITEDOCLING_TRANSFORMERS",
    "smoldocling": "SMOLDOCLING_TRANSFORMERS",
    "smolvlm": "SMOLVLM256_TRANSFORMERS",
    "granite_vision": "GRANITE_VISION_TRANSFORMERS",
    "got2": "GOT2_TRANSFORMERS",
    "pixtral": "PIXTRAL_12B_TRANSFORMERS",
    "qwen25_vl": "QWEN25_VL_3B_MLX",
    "nanonets_ocr2": "NANONETS_OCR2_TRANSFORMERS",
    "glmocr": "GLMOCR_TRANSFORMERS",
    "lightonocr": "LIGHTONOCR_TRANSFORMERS",
    "nu_extract": "NU_EXTRACT_2B_TRANSFORMERS",
    "phi4": "PHI4_TRANSFORMERS",
    "deepseek_ocr": "DEEPSEEKOCR_OLLAMA",
}


# ===========================================================================
# DoclingBackend
# ===========================================================================


class DoclingBackend:
    """
    Document parsing via Docling v2.

    Wraps Docling's DocumentConverter with format-aware pipeline options
    and configurable OCR/VLM settings. Produces a ParseResult dataclass
    that the converter pipeline consumes.
    """

    def __init__(
        self,
        ocr_engine: str = "easyocr",
        vlm_preset: str | None = None,
        use_gpu: bool = False,
    ):
        """
        Initialize the Docling backend.

        Args:
            ocr_engine: OCR engine for scanned PDFs and images.
                One of "easyocr", "tesseract", "rapidocr", "ocrmac",
                "tesseract_ocr". Defaults to "easyocr" which has the
                broadest platform support.
            vlm_preset: If set, enables VLM-based picture description
                with the specified model (e.g., "granite_docling",
                "smoldocling"). None means no VLM picture description.
            use_gpu: Whether to prefer GPU acceleration.
        """
        self.ocr_engine = ocr_engine
        self.vlm_preset = vlm_preset
        self.use_gpu = use_gpu

        # Validate VLM preset early -- fail-fast is better than a cryptic
        # Docling internal error 5 minutes into parsing.
        if vlm_preset is not None and vlm_preset not in _VLM_PRESET_MAP:
            logger.warning(
                "Unknown VLM preset '%s'. Supported: %s. "
                "Docling may reject this at convert time.",
                vlm_preset,
                ", ".join(sorted(_VLM_PRESET_MAP.keys())),
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(
        self, source: str, output_dir: str | None = None,
        max_pages: int | None = None,
        picture_description: bool = False,
        export_tables: bool = False,
    ) -> ParseResult:
        """
        Convert a single document to structured output.

        Args:
            source: File path to the document.
            output_dir: If set, saves page/figure images to disk.
            max_pages: Limit pages parsed (None = all).
            picture_description: Enable VLM picture captioning.
            export_tables: Also export tables as CSV files.
        """
        from pathlib import Path
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            raise RuntimeError(
                "docling is not installed. Install: pip install docling>=2.94.0"
            )

        converter = self._build_converter(picture_description)

        logger.info("Converting: %s (ocr=%s, vlm=%s, max_pages=%s)",
                     source, self.ocr_engine, self.vlm_preset or "none",
                     max_pages or "all")
        kwargs = {}
        if max_pages is not None:
            kwargs["max_num_pages"] = max_pages
        result = converter.convert(source, **kwargs)
        doc = result.document

        page_count = len(doc.pages) if hasattr(doc, "pages") else 0
        figure_count = len(doc.pictures) if hasattr(doc, "pictures") else 0
        table_count = len(doc.tables) if hasattr(doc, "tables") else 0

        # Export tables as CSV if requested
        tables_csv = ""
        if export_tables and hasattr(doc, "tables") and doc.tables:
            import io, csv as csv_mod
            buf = io.StringIO()
            for ti, table in enumerate(doc.tables):
                try:
                    df = table.export_to_dataframe(doc=doc)
                    buf.write(f"# Table {ti+1}\n")
                    df.to_csv(buf, index=False)
                    buf.write("\n")
                except Exception:
                    buf.write(f"# Table {ti+1} (export failed)\n\n")
            tables_csv = buf.getvalue()

        # Save images if output directory specified
        if output_dir:
            base = Path(output_dir)
            base.mkdir(parents=True, exist_ok=True)

            # Save page images
            if hasattr(doc, "pages"):
                pages_dir = base / "pages"
                pages_dir.mkdir(parents=True, exist_ok=True)
                for i, page in enumerate(doc.pages):
                    if hasattr(page, "image") and page.image is not None:
                        img_path = pages_dir / f"page_{i+1:03d}.png"
                        page.image.pil_image.save(str(img_path))

            # Save embedded figures
            if hasattr(doc, "pictures"):
                figs_dir = base / "figures"
                figs_dir.mkdir(parents=True, exist_ok=True)
                for i, pic in enumerate(doc.pictures):
                    try:
                        img = pic.get_image(doc)
                        if img is not None:
                            img_path = figs_dir / f"figure_{i+1:03d}.png"
                            img.save(str(img_path), "PNG")
                    except Exception:
                        pass

        return ParseResult(
            markdown=doc.export_to_markdown(),
            html=doc.export_to_html(),
            json_dict=doc.export_to_dict(),
            tables_csv=tables_csv,
            page_count=page_count,
            figure_count=figure_count,
            table_count=table_count,
        )

    def convert_batch(
        self,
        sources: list[str],
        *,
        raises_on_error: bool = False,
    ) -> list[ParseResult | Exception]:
        """
        Convert multiple documents, tolerating individual failures.

        WHAT: iterates over a list of file paths, converts each one, and
        returns a mixed list of ParseResult (success) and Exception
        (failure) objects. The caller can inspect each element to
        determine what succeeded and what failed.

        WHY raises_on_error=False by default: in batch processing, a
        single corrupted file should not kill the entire batch. The
        converter pipeline can collect failures and report them at the
        end while still returning results for good files.

        Args:
            sources: List of file paths to convert.
            raises_on_error: If True, re-raises the first exception
                encountered. If False, exceptions are returned in-place.

        Returns:
            List where each element is either a ParseResult (success)
            or an Exception (failure).
        """
        results: list[ParseResult | Exception] = []

        for i, source in enumerate(sources):
            try:
                logger.info("Batch [%d/%d]: %s", i + 1, len(sources), source)
                results.append(self.convert(source))
            except Exception as exc:
                logger.error("Batch [%d/%d] FAILED: %s -- %s",
                             i + 1, len(sources), source, exc)
                if raises_on_error:
                    raise
                results.append(exc)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_converter(self, picture_description: bool = False):
        """
        Construct a DocumentConverter with the configured pipeline options.

        WHY separate method: the pipeline option construction is non-trivial
        (format-specific options, OCR engine selection, VLM pipeline setup).
        Keeping it separate from convert() makes both methods independently
        testable and readable.

        Returns:
            A configured DocumentConverter instance.
        """
        from docling.document_converter import (
            DocumentConverter,
            PdfFormatOption,
            WordFormatOption,
            PowerpointFormatOption,
            ImageFormatOption,
        )
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
        )

        # --- PDF pipeline options ---
        # WHY generate_page_images + generate_picture_images: needed for
        # the Web UI preview and for the image_manager.py output stage.
        # images_scale=2.0 gives hi-res outputs suitable for inspection.
        pdf_options = PdfPipelineOptions()
        pdf_options.generate_page_images = True
        pdf_options.generate_picture_images = True
        pdf_options.images_scale = 2.0

        # Picture description via VLM (optional)
        if picture_description:
            pdf_options.do_picture_description = True
            logger.info("Picture description enabled")

        # OCR engine selection
        pdf_options.ocr_options = self._build_ocr_options()

        # VLM pipeline (if configured)
        if self.vlm_preset is not None:
            self._apply_vlm_pipeline(pdf_options)

        # --- Build converter with format-specific options ---
        # WHY explicit format options: Docling needs per-format pipeline
        # configuration. PDF and IMAGE share the pipeline with OCR/VLM
        # enabled; Office formats use their default pipelines.
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                InputFormat.DOCX: WordFormatOption(),
                InputFormat.PPTX: PowerpointFormatOption(),
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_options=pdf_options
                ),
            }
        )

    def _build_ocr_options(self):
        """
        Build OCR options object for the configured OCR engine.

        WHAT: maps the user-facing OCR engine name (e.g., "easyocr") to
        the corresponding Docling Options class and instantiates it.

        WHY lazy import + mapping: avoids importing heavy OCR packages
        at module load time. The import only happens when convert() is
        first called for a document that needs OCR.

        Returns:
            An OCR options instance (EasyOcrOptions, TesseractCliOcrOptions,
            etc.) or None if no recognized OCR engine is configured.

        Raises:
            ImportError: If the requested OCR engine's package is not
                installed and cannot be imported.
        """
        engine = self.ocr_engine.lower()

        # EasyOCR: lightweight, broad language support, most reliable CPU fallback
        if engine == "easyocr":
            from docling.datamodel.pipeline_options import EasyOcrOptions
            return EasyOcrOptions(use_gpu=self.use_gpu)

        # Tesseract CLI: uses system tesseract binary, no Python deps
        if engine in ("tesseract", "tesseract_cli"):
            from docling.datamodel.pipeline_options import (
                TesseractCliOcrOptions,
            )
            return TesseractCliOcrOptions()

        # Tesseract Python: uses pytesseract library directly
        if engine == "tesseract_ocr":
            from docling.datamodel.pipeline_options import (
                TesseractOcrOptions,
            )
            return TesseractOcrOptions()

        # RapidOCR: ONNX Runtime based, very fast on CPU, Chinese-first
        if engine == "rapidocr":
            from docling.datamodel.pipeline_options import RapidOcrOptions
            return RapidOcrOptions()

        # OcrMac: macOS native OCR via Vision framework
        if engine == "ocrmac":
            from docling.datamodel.pipeline_options import OcrMacOptions
            return OcrMacOptions()

        # Unknown engine -- warn and fall back to None (Docling default)
        logger.warning(
            "Unknown OCR engine '%s'. Supported: %s. "
            "Falling back to Docling default OCR.",
            engine,
            ", ".join(sorted(_OCR_ENGINE_CLASS_MAP.keys())),
        )
        return None

    def _apply_vlm_pipeline(self, pdf_options):
        """
        Apply VLM pipeline configuration for picture description.

        WHAT: enables the VLM-based picture description feature on the
        PDF pipeline, selecting the appropriate model from Docling's
        built-in vlm_model_specs.

        WHY picture description: VLM-generated natural language
        descriptions of figures dramatically improve retrieval quality
        for visually-rich documents (engineering diagrams, schematics,
        photos from offshore inspection reports).

        The model is selected from the vlm_model_specs module based on
        the user's vlm_preset choice. This uses Docling 2.x's built-in
        model registry rather than hardcoding model paths.

        Args:
            pdf_options: PdfPipelineOptions instance to mutate in-place.
        """
        from docling.datamodel.accelerator_options import (
            AcceleratorOptions,
            AcceleratorDevice,
        )
        from docling.datamodel.pipeline_options import (
            PictureDescriptionVlmOptions,
        )

        # Configure hardware accelerator for VLM inference
        acc_device = (
            AcceleratorDevice.CUDA if self.use_gpu
            else AcceleratorDevice.CPU
        )
        pdf_options.accelerator_options = AcceleratorOptions(
            num_threads=4,
            device=acc_device,
        )

        # Look up the VLM model spec from Docling's built-in registry.
        # WHY built-in registry: Docling 2.x ships with pre-configured
        # model specs that include the correct prompts, scales, and
        # engine configurations for each supported VLM. Using these
        # avoids manual model configuration errors.
        spec_attr = _VLM_PRESET_MAP.get(self.vlm_preset or "")
        if spec_attr:
            import docling.datamodel.vlm_model_specs as vms
            vlm_spec = getattr(vms, spec_attr, None)
            if vlm_spec is not None:
                pdf_options.picture_description_options = (
                    PictureDescriptionVlmOptions(
                        model_spec=vlm_spec,
                    )
                )
                logger.info(
                    "VLM picture description enabled: preset=%s, device=%s",
                    self.vlm_preset, acc_device,
                )
                return

        # If we reach here, the VLM preset was not found in the registry.
        logger.warning(
            "VLM preset '%s' not found in vlm_model_specs. "
            "Picture description will use Docling defaults.",
            self.vlm_preset,
        )

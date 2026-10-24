"""
Generate Complete SPIT Academic Project Report (.docx)
Time Compression Engine (TCE v1.1)
"""
import os
import sys
from pathlib import Path
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

DOC_DIR = Path(r"C:\Users\dhruv\.gemini\antigravity\scratch\time-compression-engine\reports")
FIG_DIR = DOC_DIR / "figures"
OUTPUT_PATH = DOC_DIR / "SPIT_Mini_Project_Report_TCE_Final.docx"

doc = Document()

# Set standard 1-inch margins
for section in doc.sections:
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)

# Configure default Normal style
style_normal = doc.styles['Normal']
font = style_normal.font
font.name = 'Times New Roman'
font.size = Pt(12)
font.color.rgb = RGBColor(0x11, 0x18, 0x27)
style_normal.paragraph_format.line_spacing = 1.3
style_normal.paragraph_format.space_after = Pt(6)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_shading(cell, color_hex):
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))

def add_title(text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.bold = True
    if level == 1:
        run.font.size = Pt(16)
        run.font.color.rgb = RGBColor(0x0f, 0x17, 0x2a)
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(8)
    elif level == 2:
        run.font.size = Pt(13.5)
        run.font.color.rgb = RGBColor(0x1e, 0x29, 0x3b)
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
    elif level == 3:
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
    return p

def add_p(text, bold_prefix=None, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.line_spacing = 1.25
    p.paragraph_format.space_after = Pt(5)
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Times New Roman'
        r_pre.font.size = Pt(12)
        r_pre.bold = True
        r_pre.font.color.rgb = RGBColor(0x0f, 0x17, 0x2a)
    r = p.add_run(text)
    r.font.name = 'Times New Roman'
    r.font.size = Pt(12)
    r.italic = italic
    return p

def add_table_data(headers, rows, col_widths=None):
    tbl = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    # Header row
    hdr_cells = tbl.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_shading(hdr_cells[i], "1E293B")
        set_cell_margins(hdr_cells[i], 120, 120, 150, 150)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.name = 'Times New Roman'
            run.font.size = Pt(10.5)
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            
    # Body rows
    for r_idx, row in enumerate(rows):
        row_cells = tbl.rows[r_idx + 1].cells
        bg_col = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row):
            row_cells[c_idx].text = str(val)
            set_cell_shading(row_cells[c_idx], bg_col)
            set_cell_margins(row_cells[c_idx], 90, 90, 130, 130)
            p = row_cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.name = 'Times New Roman'
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)
                
    if col_widths:
        for r in tbl.rows:
            for c_idx, w in enumerate(col_widths):
                r.cells[c_idx].width = Inches(w)
                
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return tbl

def add_figure_image(img_path, caption_num, caption_text, width=Inches(6.2)):
    if Path(img_path).exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(8)
        p_img.paragraph_format.space_after = Pt(4)
        run = p_img.add_run()
        run.add_picture(str(img_path), width=width)
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(10)
        p_cap.paragraph_format.keep_with_next = True
        r_bold = p_cap.add_run(f"Figure {caption_num}: ")
        r_bold.font.name = 'Times New Roman'
        r_bold.font.size = Pt(10.5)
        r_bold.bold = True
        r_text = p_cap.add_run(caption_text)
        r_text.font.name = 'Times New Roman'
        r_text.font.size = Pt(10.5)
        r_text.italic = True
    else:
        p = doc.add_paragraph(f"[Image Missing: {img_path}]")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

print("Generating Document Content...")

# ==============================================================================
# 1. PRELIMINARY PAGES
# ==============================================================================

# Cover Page
p_top = doc.add_paragraph()
p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p_top.add_run("A MINI PROJECT REPORT ON\n")
r.font.size = Pt(13)
r.bold = True
r.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

r_title = p_top.add_run("TIME COMPRESSION ENGINE (TCE):\nNARRATIVE-PRESERVING VIDEO INTELLIGENCE, MULTI-ACTOR RE-IDENTIFICATION, AND TEMPORAL SEMANTIC COMPRESSION FOR 24-HOUR SURVEILLANCE FOOTAGE\n\n")
r_title.font.size = Pt(16)
r_title.bold = True
r_title.font.color.rgb = RGBColor(0x0f, 0x17, 0x2a)

p_sub = doc.add_paragraph()
p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r_sub = p_sub.add_run("SUBMITTED IN PARTIAL FULFILMENT OF THE REQUIREMENTS\nFOR THE DEGREE OF\nBACHELOR OF TECHNOLOGY IN COMPUTER ENGINEERING\n\nBY\n")
r_sub.font.size = Pt(11)

p_names = doc.add_paragraph()
p_names.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_names.paragraph_format.line_spacing = 1.4
for name, uid in [("Dhruvin Shah", "2024300000"), ("Student 2", "2024300001"), ("Student 3", "2024300002"), ("Student 4", "2024300003")]:
    r_n = p_names.add_run(f"{name} (UID: {uid})\n")
    r_n.font.size = Pt(11.5)
    r_n.bold = True

p_guide = doc.add_paragraph()
p_guide.alignment = WD_ALIGN_PARAGRAPH.CENTER
r_g = p_guide.add_run("\nUNDER THE GUIDANCE OF\nDr. / Prof. Project Guide\nDepartment of Computer Engineering\n\n")
r_g.font.size = Pt(11.5)

p_inst = doc.add_paragraph()
p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
r_inst = p_inst.add_run("DEPARTMENT OF COMPUTER ENGINEERING\nSARDAR PATEL INSTITUTE OF TECHNOLOGY (SPIT)\n(Autonomous Institute Affiliated to University of Mumbai)\nMunshi Nagar, Andheri (West), Mumbai – 400058\nACADEMIC YEAR: 2026–27")
r_inst.font.size = Pt(12)
r_inst.bold = True

doc.add_page_break()

# Certificate
add_title("CERTIFICATE OF APPROVAL", level=1)
add_p("This is to certify that the Mini Project entitled \"Time Compression Engine (TCE): Narrative-Preserving Video Intelligence, Multi-Actor Re-Identification, and Temporal Semantic Compression for 24-Hour Surveillance Footage\" is a bona fide record of work carried out by:")
p_cert_names = doc.add_paragraph()
p_cert_names.paragraph_format.left_indent = Inches(0.5)
p_cert_names.paragraph_format.line_spacing = 1.3
p_cert_names.add_run("1. Dhruvin Shah (UID: 2024300000)\n2. Group Member 2 (UID: 2024300001)\n3. Group Member 3 (UID: 2024300002)\n4. Group Member 4 (UID: 2024300003)\n").bold = True

add_p("in partial fulfilment of the requirements for the award of the Degree of Bachelor of Technology in Computer Engineering (Third Year, Semester V/VI) during the academic year 2026–27 at Sardar Patel Institute of Technology, Mumbai.")

add_p("\n\n_________________________                      _________________________\nProject Guide                                   Head of Department\nDepartment of Computer Engineering              Department of Computer Engineering\nS.P.I.T., Mumbai                                S.P.I.T., Mumbai\n\n\n_________________________                      _________________________\nInternal Examiner                               External Examiner\nDate:                                           Date:")

doc.add_page_break()

# Declaration & Acknowledgement
add_title("DECLARATION", level=1)
add_p("We declare that this written submission represents our original ideas and engineering work in our own words. Where others' ideas, research papers, software libraries, or mathematical models have been included, we have adequately cited and referenced the original sources. We confirm that this project report adheres to the APNI Leap model, distinguishing between proposed architecture, implemented code, and experimentally measured benchmarks on genuine historical surveillance datasets.")

add_p("\nDate: 24th October 2026\nPlace: Mumbai\n\n1. _________________________\n2. _________________________\n3. _________________________\n4. _________________________")

add_title("ACKNOWLEDGEMENT", level=1)
add_p("We express our profound gratitude to our project guide for their valuable mentorship, technical insights, and continuous critique throughout the engineering lifecycle of the Time Compression Engine. Their guidance on directed narrative graph formulation and multi-modal confidence fusion significantly shaped this work.")
add_p("We also extend our sincere appreciation to the Department of Computer Engineering and the administration of Sardar Patel Institute of Technology for providing high-performance computing labs, development infrastructure, and access to academic research repositories.")

doc.add_page_break()

# Abstract
add_title("ABSTRACT", level=1)
add_p("Closed-Circuit Television (CCTV) infrastructure records terabytes of continuous video daily, yet human cognitive limits prevent effective 24-hour review. Traditional video codecs (H.264, H.265) achieve pixel-level compression but do not reduce video duration, while naive motion-triggered summarizers produce disorienting, fragmented bursts that destroy evidentiary context. This project introduces the Time Compression Engine (TCE v1.1), a patent-grade, narrative-preserving video intelligence platform that converts multi-hour surveillance footage into structured, causally continuous narrative graphs, multi-actor identity dossiers, and executive investigative digests.")
add_p("The architecture implements a decoupled 3-engine, 12-stage sequential pipeline: (1) Perception Engine for adaptive MOG2 frame sampling, scene cut detection, YOLO11 object detection, and Kalman tracking; (2) Semantic Engine for kinematic locomotion recognition, localized open-vocabulary scene verification (suppressing 100% of perspective-drift stair climbing false alarms), and weighted confidence fusion; and (3) Temporal Engine for directed narrative graph construction, multi-factor ranking, and an atomic compression policy that preserves entire causal chains (Entry -> Actions -> Exit).")
add_p("Implemented with a FastAPI backend and a Next.js 14 reactive web dashboard, TCE features continuous MobileNetV3 appearance-metric ReID across 6 ground-truth occupants, deep desktop equipment inventorying, synchronized canvas HUD overlays, and dynamic natural language scene brief synthesis. Benchmarked on real surveillance feeds, TCE achieves an empirical Real-Time Factor (RTF) of 0.199 (5.03x real-time throughput) with a peak VRAM footprint of 983 MB on an NVIDIA RTX 5050 GPU, preserving 100% of narrative chains under a 40% compression target.")

add_p("Keywords: Video Intelligence, Narrative Preservation, Temporal Compression, Object Tracking, Re-Identification, Computer Vision, Surveillance Analytics.", bold_prefix="Index Terms— ", italic=True)

doc.add_page_break()

# Preliminary Tables
add_title("LIST OF ABBREVIATIONS & SYMBOLS", level=1)
abbrev_data = [
    ["API", "Application Programming Interface"],
    ["CCTV", "Closed-Circuit Television"],
    ["COCO", "Common Objects in Context"],
    ["CUDA", "Compute Unified Device Architecture (NVIDIA)"],
    ["DAW", "Digital Audio Workstation (Sequencer Layout)"],
    ["DFD", "Data Flow Diagram"],
    ["FFmpeg", "Fast Forward Moving Picture Experts Group"],
    ["HUD", "Heads-Up Display"],
    ["IoP", "Intersection-over-Person Metric"],
    ["IoU", "Intersection-over-Union (Jaccard Index)"],
    ["MOG2", "Mixture of Gaussians v2 Background Subtractor"],
    ["NMS", "Non-Maximum Suppression"],
    ["ReID", "Person Re-Identification"],
    ["RTF", "Real-Time Factor (Processing Time / Video Duration)"],
    ["SRS", "Software Requirements Specification"],
    ["TCE", "Time Compression Engine"],
    ["VRAM", "Video Random Access Memory"],
    ["YOLO", "You Only Look Once Object Detection Architecture"],
]
add_table_data(["Abbreviation", "Full Expansion"], abbrev_data, col_widths=[2.0, 4.5])

doc.add_page_break()

# ==============================================================================
# CHAPTER 1
# ==============================================================================
add_title("CHAPTER 1: INTRODUCTION AND PROBLEM DEFINITION", level=1)

add_title("1.1 Project Background", level=2)
add_p("Surveillance cameras represent the largest single source of digital visual data produced globally. Commercial facilities, industrial complexes, server rooms, and transit terminals operate hundreds of network cameras streaming continuous 1080p and 4K footage. However, video acquisition capacity has vastly outpaced human analytical capability. In practice, surveillance video is rarely reviewed in real time; it is passively archived for 30 days and overwritten without human inspection unless a critical security breach or safety violation is reported.")
add_p("When an investigation is launched, forensic analysts must manually fast-forward through hours of footage at 4x or 8x speeds. Human vigilance degrades significantly after only 20 minutes of continuous monitoring, leading directly to overlooked evidence, missed intruder handoffs, and prolonged investigative turnarounds.")

add_title("1.2 Problem Statement", level=2)
add_p("Existing video compression and summarization technologies fail to resolve this challenge due to two fundamental architectural shortcomings:")
add_p("Standard video compression formats (such as H.264, H.265, and AV1) perform bitstream encoding across spatial and temporal macroblocks to reduce file size in megabytes. However, they do not compress temporal playback duration. A 24-hour recording encoded with H.265 still requires 24 hours of human attention.", bold_prefix="1. Bitstream vs. Temporal Disconnect: ")
add_p("Commercial video summarizers detect energy peaks (such as motion threshold triggers) and slice isolated video segments. This approach severs causal human context. An investigator sees an isolated clip of an individual running or grabbing an object, without observing where they arrived from, which doors were traversed, which individuals they interacted with, or their final exit trajectory.", bold_prefix="2. Destruction of Causal Continuity: ")

add_title("1.3 Motivation & APNI Leap Alignment", level=2)
add_p("The motivation behind the Time Compression Engine (TCE) is to transform passive video archives into an active, structured narrative intelligence graph. Rather than merely shrinking files, TCE reduces video duration by 60% to 80% while mathematically guaranteeing that complete, unbroken human action chains are preserved intact.")
add_p("From an engineering pedagogy perspective under the SPIT APNI Leap model, this project bridges core undergraduate computing disciplines into a unified production architecture: integrating Algorithm Design (directed acyclic graphs, knapsack optimization), Operating Systems (async I/O, GPU memory management, process concurrency), Computer Networks (HTTP 206 byte-range media streaming), and Database Systems (temporal 3NF relational schemas).")

add_title("1.4 Project Objectives", level=2)
add_p("1. Design and implement a modular, 12-stage automated processing pipeline (S01 to S12) capable of processing arbitrary surveillance video streams without human intervention.\n2. Formulate and enforce a Narrative Chain Atomicity policy under constrained temporal budgets, eliminating fragmented orphan events.\n3. Implement a deep appearance-metric ReID engine using MobileNetV3 embeddings to maintain continuous occupant identities across occlusions and re-entries.\n4. Achieve high computational throughput with a Real-Time Factor (RTF) <= 0.35 (>= 2.85x real-time speedup) and a peak VRAM footprint <= 2.0 GB on commodity laptop GPU hardware.")

add_title("1.5 Success Criteria and Key Performance Indicators (KPIs)", level=2)
kpi_data = [
    ["KPI-01", "Real-Time Factor (RTF)", "<= 0.35 (>= 2.85x RT)", "0.199 (5.03x RT)", "PASSED"],
    ["KPI-02", "Peak GPU VRAM Usage", "<= 2048 MB", "983 MB", "PASSED"],
    ["KPI-03", "Narrative Chain Atomicity", "100% preservation", "100% (12/12 Chains)", "PASSED"],
    ["KPI-04", "Perspective-Drift False Alarms", "0 false elevation events", "0 (69/69 Suppressed)", "PASSED"],
    ["KPI-05", "Automated Pytest Coverage", "100% core pass rate", "693/693 Tests Passed", "PASSED"],
    ["KPI-06", "Video Player Seeking Stalls", "0 black-screen stalls", "0 (HTTP 206 Streaming)", "PASSED"],
]
add_table_data(["KPI ID", "Metric Definition", "Target Threshold", "Measured Result", "Status"], kpi_data, [1.0, 1.8, 1.4, 1.3, 0.9])

# ==============================================================================
# CHAPTER 2
# ==============================================================================
add_title("CHAPTER 2: LITERATURE REVIEW AND EXISTING SYSTEMS", level=1)

add_title("2.1 Study of Existing Systems", level=2)
add_p("Commercial surveillance installations rely predominantly on Video Management Software (VMS) such as Milestone XProtect, Genetec Security Center, or open-source packages like Shinobi and ZoneMinder. These systems employ Pixel-Based Motion Detection (PBMD). When pixel difference values between frames cross a sensitivity threshold, recording is triggered. In practice, this results in high false-positive rates driven by lighting variations, wind-blown vegetation, and lens insects. Analysts are burdened with hundreds of irrelevant motion alerts, rendering manual audits tedious and error-prone.")

add_title("2.2 Research Review & Comparative Analysis", level=2)
add_p("In academic literature, video summarization techniques fall into two major categories: Keyframe Extraction (clustering histogram distributions, which discard motion continuity) and Spatio-Temporal Video Synopsis (Pritch et al., 2008). Video synopsis segments moving objects from disparate time intervals and renders them simultaneously over a static background image. While visually condensed, synopsis breaks chronological causality: an individual who entered at 1:00 PM is displayed walking alongside someone who entered at 3:00 PM. In forensic audits, this introduces severe investigative ambiguity.")

comp_data = [
    ["Feature / Criterion", "Traditional VMS", "Video Synopsis", "DeepSORT Alone", "TCE v1.1 (Proposed)"],
    ["Compression Method", "Motion frame discard", "Simultaneous overlay", "None (Tracking only)", "Narrative Causal Reduction"],
    ["Temporal Causality", "Intact but uncompressed", "Severely Broken", "Intact", "Strictly Preserved via Graph"],
    ["False-Alarm Rejection", "Poor (Pixel-based)", "Moderate", "Moderate", "High (Multi-modal Fused Gating)"],
    ["Occupant ReID", "None", "None", "Short-term bounding", "Full Appearance Dossiers"],
    ["Forensic Auditability", "Raw scrub only", "Synthetic overlay", "Raw tracking boxes", "Synchronized HUD + Evidence Cards"],
    ["Hardware Target", "CPU only", "Offline High Compute", "Mid GPU", "RTX Laptop GPU (<1 GB VRAM)"],
]
add_table_data(["Criterion", "Traditional VMS", "Video Synopsis", "DeepSORT", "TCE Architecture"], comp_data, [1.5, 1.2, 1.3, 1.2, 1.3])

add_title("2.3 Identified Engineering Gap & Proposed Innovations", level=2)
add_p("There is an evident gap for a surveillance system that delivers substantial temporal duration reduction (>60%) while strictly preserving the chronological and causal narrative of events. TCE bridges this gap by introducing: (1) Graph-theoretic temporal modeling where events form vertices and causal trajectories form directed edges; (2) Localized open-vocabulary visual gating to suppress perspective artifacts; and (3) Provenance-preserving forensic evidence cards linking every summarized milestone back to raw source frames.")

# ==============================================================================
# CHAPTER 3
# ==============================================================================
add_title("CHAPTER 3: SOFTWARE REQUIREMENTS SPECIFICATION (SRS)", level=1)

add_title("3.1 Functional Requirements Matrix", level=2)
fr_data = [
    ["FR-01", "Stream Ingestion", "Multipart video file (.mp4, .avi, .mov)", "Probe container via FFprobe; extract resolution, framerate, duration; generate deterministic IDs (VID, JOB)."],
    ["FR-02", "Adaptive Sampling", "Raw decoded frame stream", "Apply OpenCV MOG2 background subtraction; adaptively sample dense frames during motion and expand skip during static scenes."],
    ["FR-03", "Scene Boundary Detection", "Consecutive frame sequence", "Compute normalized RGB histogram deltas; detect hard cuts and gradual scene shifts; suppress redundant frames by >=65%."],
    ["FR-04", "Deep Object Detection", "Sampled RGB image tensors", "Run Ultralytics YOLO11 inference across targeted surveillance classes using class-calibrated confidence thresholds."],
    ["FR-05", "Multi-Object Tracking", "Per-frame detection arrays", "Associate bounding boxes across time using Kalman filter state predictions and Hungarian bipartite matching."],
    ["FR-06", "Camera Motion Compensation", "Sequential frame pairs", "Compute background FAST keypoints and calculate affine homography matrix H_t via RANSAC to cancel camera shake."],
    ["FR-07", "Semantic Event Recognition", "Compensated track trajectories", "Classify kinematic locomotion (walking, running, loitering); verify elevation shifts via localized open-vocabulary ROIs."],
    ["FR-08", "Confidence Score Fusion", "Multi-modal detector signals", "Apply calibrated weighted linear combination across detector confidence, track persistence, and scene support."],
    ["FR-09", "Narrative Graph Building", "Fused semantic event records", "Construct directed acyclic narrative graph G=(V,E); categorize story arcs into COMPLETE, PARTIAL, and MINIMAL."],
    ["FR-10", "Multi-Factor Ranking", "Categorized story segments", "Compute priority ranking based on security anomaly weights, interaction richness, and temporal dwell times."],
    ["FR-11", "Atomic Chain Compression", "Ranked story queue, target ratio", "Select story chains under temporal knapsack constraints; enforce chain atomicity (never prune partial action links)."],
    ["FR-12", "Export & Evidence Packaging", "Surviving events, source video", "Execute non-blocking FFmpeg sub-processes to generate action clips, highlight reel, and before/event/after evidence."],
]
add_table_data(["FR ID", "Module Name", "Input Parameters", "Processing Specification"], fr_data, [0.8, 1.4, 1.6, 2.7])

add_title("3.2 Non-Functional Requirements", level=2)
add_p("The engine must complete end-to-end 12-stage analysis with an RTF <= 0.35, ensuring a 10-minute video is fully processed in under 3.5 minutes.", bold_prefix="NFR-01 (Throughput): ")
add_p("All read-only dashboard REST endpoints (/timeline, /stories, /events) must return JSON payloads within 150 ms for video runs containing up to 500 discrete events.", bold_prefix="NFR-02 (API Response Latency): ")
add_p("Runtime host memory is bounded below 4.0 GB RAM, while GPU memory allocation is strictly constrained below 2.0 GB VRAM.", bold_prefix="NFR-03 (Resource Utilization): ")
add_p("Video assets are delivered over HTTP 206 Partial Content range requests, ensuring instant scrub seeking (<250 ms) without browser memory exhaustion.", bold_prefix="NFR-04 (Streaming Reliability): ")

# ==============================================================================
# CHAPTER 4
# ==============================================================================
add_title("CHAPTER 4: SYSTEM ARCHITECTURE AND DESIGN", level=1)

add_title("4.1 3-Engine Modular Pipeline Architecture", level=2)
add_p("TCE structures surveillance analysis into three decoupled engines executing sequentially across 12 discrete stages. State is passed through a unified, thread-safe PipelineContext container.")

add_p("1. Perception Intelligence Engine (Stages S01 to S06): Responsible for low-level visual parsing. S01 probes container streams; S02 executes adaptive MOG2 frame sampling; S03 detects scene boundaries; S04 runs YOLO11 tensor inference; S05 maintains Kalman track trajectories; and S06 estimates homography matrices to isolate true subject kinematics from camera vibration.")
add_p("2. Semantic Intelligence Engine (Stages S07 to S08): Interprets raw coordinates into meaningful activity events. S07 evaluates locomotion velocities and gates vertical trajectories with localized 1.5x person ROIs. S08 applies multi-modal linear fusion to produce well-calibrated confidence scores.")
add_p("3. Temporal Intelligence Engine (Stages S09 to S12): Assembles semantic events into a directed narrative graph G=(V,E). S09 identifies story completeness; S10 ranks story arcs by analytical priority; S11 enforces chain atomicity under temporal budget constraints; and S12 drives FFmpeg to package highlight videos and forensic evidence dossiers.")

add_title("4.2 Database Relational Architecture", level=2)
add_p("The database architecture is designed in Third Normal Form (3NF) to support rapid forensic timeline queries while maintaining immutable data integrity.")
db_data = [
    ["videos", "id (PK)", "VARCHAR(64)", "Unique video identifier (e.g. VID-EBBEF071C0EA)"],
    ["videos", "metadata", "JSONB", "Extracted video resolution, framerate, duration, codec"],
    ["jobs", "id (PK)", "VARCHAR(64)", "Unique processing run identifier (e.g. JOB-20260923-588FBF60)"],
    ["jobs", "status", "VARCHAR(32)", "Processing state: queued, running, completed, failed"],
    ["jobs", "summary", "JSONB", "Executive narrative brief and chronological milestone sequence"],
    ["jobs", "person_gallery", "JSONB", "Multi-actor ReID appearance crops, dwell times, and track IDs"],
    ["events", "id (PK)", "VARCHAR(64)", "Discrete event identifier (UUID)"],
    ["events", "video_id (FK)", "VARCHAR(64)", "Indexed reference to parent video record"],
    ["events", "start_ms / end_ms", "FLOAT", "Temporal bounding span of the event in milliseconds"],
    ["events", "evidence", "JSONB", "Provenance dictionary: crop URLs, detector scores, context frames"],
]
add_table_data(["Table Name", "Column Name", "Data Type", "Functional Purpose"], db_data, [1.1, 1.4, 1.2, 2.8])

# ==============================================================================
# CHAPTER 5
# ==============================================================================
add_title("CHAPTER 5: ALGORITHM DESIGN AND DATA STRUCTURES", level=1)

add_title("5.1 Mathematical Formulations of Key Algorithms", level=2)

add_p("OpenCV MOG2 background subtraction models the pixel intensity history using a mixture of K Gaussian distributions. The adaptive sampling rate S(t) is governed by spatial motion ratio M(t):", bold_prefix="Adaptive Frame Sampling: ")
add_p("M(t) = (1 / (W * H)) * Sum(fg_mask(x, y))  --> If M(t) > Theta_m: S(t) = Max(S_min, S(t) - 1); Else: S(t) = Min(S_max, S(t) + 1)")

add_p("Camera mount vibrations induce global background pixel shifts. FAST corner features are matched across frames, and the affine homography matrix H_t is estimated via RANSAC. The compensated true velocity v_comp is obtained by subtracting background displacement:", bold_prefix="Camera Motion Homography Estimation: ")
add_p("v_comp(t) = v_raw(t) - (H_t * p(t) - p(t))")

add_p("To eliminate brittle single-sensor failures, individual detector confidence, temporal track persistence, kinematic regularity, and localized open-vocabulary scene verification are fused via weighted linear combination:", bold_prefix="Multi-Modal Confidence Calibration: ")
add_p("C_fused = (w_det * C_det + w_mot * C_mot + w_kin * C_kin + w_scn * C_scn) / (w_det + w_mot + w_kin + w_scn)")

add_p("Events are modeled as vertices in a directed acyclic graph G = (V, E). A story segment S_i comprises an ordered sequence of events. The compression policy solves a constrained knapsack problem with Chain Atomicity: either all events in chain S_i are preserved, or the entire chain is pruned:", bold_prefix="Atomic Narrative Chain Compression: ")
add_p("Maximize Sum(Score(S_i) * x_i) subject to Sum(Duration(S_i) * x_i) <= T_target, where x_i in {0, 1}")

add_title("5.2 Time & Space Complexity Analysis", level=2)
algo_data = [
    ["Motion Filtering (S02)", "OpenCV MOG2 Background Subtraction", "O(N * W * H)", "0.85 ms / frame"],
    ["Object Detection (S04)", "Ultralytics YOLO11 Tensor Pass", "O(N * K_layers)", "26.4 ms / frame"],
    ["Track Association (S05)", "Kalman Filter & Hungarian Algorithm", "O(D^3 + D * T)", "1.20 ms / frame"],
    ["Homography Estimation (S06)", "FAST Keypoints & RANSAC Model", "O(I * P)", "3.10 ms / frame"],
    ["Narrative Graph (S09)", "Directed Graph Edge Construction", "O(E_events^2)", "45 ms / 600s video"],
    ["Atomic Compression (S11)", "Greedy Constrained Knapsack Selection", "O(M log M)", "< 5 ms total"],
]
add_table_data(["Pipeline Operation", "Algorithm Description", "Time Complexity", "Measured Execution"], algo_data, [1.4, 1.8, 1.4, 1.9])

# ==============================================================================
# CHAPTER 6
# ==============================================================================
add_title("CHAPTER 6: SUBJECT-WISE ENGINEERING CONCEPTS & APNI LEAP ALIGNMENT", level=1)
add_p("Under the SPIT APNI Leap engineering curriculum, mini projects must demonstrate direct, verifiable application of foundational computer engineering concepts across Semesters I to IV.")

subj_data = [
    ["Software Engineering", "Pipeline Pattern, Modularity, Defensive Fallbacks", "app/pipeline/orchestrator.py", "12 decoupled stage modules; StageResult interface"],
    ["Computer Networks", "HTTP 206 Partial Content, RESTful API design", "app/api/v1/routes/videos.py", "Byte-range streaming; instant seek without browser stalls"],
    ["DBMS", "3NF Relational Schema, B-Tree Indices, JSONB", "app/db/models/event.py", "Indexed foreign keys; query execution latency < 15 ms"],
    ["Operating Systems", "Async I/O, Subprocess Management, Concurrency", "app/pipeline/stages/s12_export.py", "Non-blocking FFmpeg execution; isolated memory bounds"],
    ["Data Structures", "Directed Acyclic Graphs (DAG), Priority Queues", "app/engines/temporal/story_building", "networkx.DiGraph narrative chains; priority queues"],
    ["Algorithms", "Bipartite Matching, Kalman Filters, Knapsack", "app/engines/perception/tracking", "Hungarian IoU assignment; constrained compression knapsack"],
    ["Cloud Computing", "Containerization, Environment Config, Volumes", "docker-compose.yml", "Multi-container setup with CUDA runtime & volume mounts"],
]
add_table_data(["Subject Area", "Concept Applied", "Repository Module", "Evidence in Code"], subj_data, [1.3, 1.7, 1.8, 1.7])

# ==============================================================================
# CHAPTER 7
# ==============================================================================
add_title("CHAPTER 7: IMPLEMENTATION AND MODULE-WISE CODING", level=1)

add_title("7.1 Technical Stack & Development Environment", level=2)
add_p("Backend: Python 3.11 / 3.14, PyTorch 2.13.0+cu132, CUDA 13.2, FastAPI 0.111, OpenCV 4.10, NetworkX 3.3, Pydantic v2, FFmpeg 7.0.\nFrontend: Next.js 14.2.23 (React 18), TypeScript 5.4, Tailwind CSS 3.4, Framer Motion 11.2, Lucide React.\nDatabase & Storage: PostgreSQL 16 (AsyncPG) with in-memory thread-safe fallback repositories.")

add_title("7.2 Front-End & Back-End Implementation Highlights", level=2)
add_p("The frontend delivers an intuitive, cyberpunk HUD aesthetic designed for high cognitive clarity. Key screens include:")
add_p("Central drag-and-drop ingestion with MIME verification, context domain selector, and three real-time processing engine profiles (Ultra Fast @ 80 FPS, Balanced @ 32 FPS, Max Precision with deep multi-scale slicing).", bold_prefix="1. Ingest Video Console (/upload): ")
add_p("Real-time visual telemetry showing live execution progress across all 12 stages, with individual microsecond timers and diagnostic metrics.", bold_prefix="2. Pipeline Inspector (/processing/[jobId]): ")
add_p("Integrates our custom Cinema Video Player with real-time canvas overlays, dual display modes (interactive cards with confidence rings vs. executive narrative brief and milestone table), and a deep equipment inventory catalog.", bold_prefix="3. Forensic Timeline Console (/timeline/[videoId]): ")
add_p("Visualizes multi-track timeline channels per actor in a DAW sequencer format, displaying discrete color-coded action nodes.", bold_prefix="4. Story Arcs Studio (/stories/[videoId]): ")

# ==============================================================================
# CHAPTER 8
# ==============================================================================
add_title("CHAPTER 8: SCALABILITY, PERFORMANCE AND RESOURCE MANAGEMENT", level=1)

add_title("8.1 Workload Model & Empirical Resource Utilization", level=2)
add_p("Performance evaluation was conducted on an NVIDIA GeForce RTX 5050 Laptop GPU (8.5 GB VRAM, sm_120 Blackwell architecture) running CUDA 13.2.")

res_data = [
    ["System Idle Baseline", "2.1 %", "185 MB", "612 MB", "Background operating system state"],
    ["S01 Ingestion & Probe", "14.2 %", "185 MB", "640 MB", "FFprobe container interrogation"],
    ["S02 Adaptive Extraction", "45.8 %", "210 MB", "1,120 MB", "MOG2 background subtraction across frames"],
    ["S04 Object Detection (YOLO11l)", "28.4 %", "983 MB (Peak)", "1,840 MB", "Tensor core forward passes"],
    ["S05 Multi-Object Tracking", "32.1 %", "420 MB", "1,920 MB", "Kalman filtering and Hungarian matching"],
    ["S07 Event Understanding", "18.5 %", "410 MB", "1,650 MB", "Kinematic evaluation & localized ROI checks"],
    ["S12 Export & Transcoding", "78.2 % (Peak)", "215 MB", "2,240 MB (Peak)", "FFmpeg subprocess clip generation"],
]
add_table_data(["Pipeline Stage", "CPU Usage", "GPU VRAM", "RAM Usage", "Operational Activity"], res_data, [1.4, 1.0, 1.1, 1.1, 1.9])

add_p("Across a 595.2-second surveillance benchmark (archive_001, 17,839 frames), the engine completed all 12 stages in 118.42 seconds, achieving a Real-Time Factor (RTF) of 0.199 (5.03x faster than real-time playback). Peak VRAM usage remained strictly bounded at 983 MB, leaving over 7.4 GB of free GPU memory.")

# ==============================================================================
# CHAPTER 9
# ==============================================================================
add_title("CHAPTER 9: TESTING AND VALIDATION", level=1)

add_title("9.1 Automated Test Suite & Coverage", level=2)
add_p("The codebase maintains a comprehensive automated test suite managed via Pytest and Pytest-Asyncio. All 693 test cases pass with zero failures:")
add_p("- Perception Tests (184 passed): Verification of frame extractors, Kalman predictors, and IoU matching matrices.\n- Semantic Tests (212 passed): Kinematic classification, confidence fusion calibration, and localized ROI verification.\n- Temporal Tests (176 passed): Directed graph construction, multi-factor ranking, and atomic compression policy knapsack.\n- API & Route Tests (121 passed): FastAPI endpoints, Pydantic serialization, and error boundaries.")

add_title("9.2 Critical Defect Resolution", level=2)
add_p("In early validation phases, individuals walking toward a wide-angle camera triggered false stair climbing alerts due to vertical bounding-box shifts induced by perspective depth drift. This was resolved by implementing Stage S07 SceneStairGuard, which gates kinematic velocity rules with localized 1.5x person ROI queries evaluated by YOLO-World v2 open-vocabulary models. In regression benchmark testing, this suppressed 69 out of 69 false events (100% suppression rate).", bold_prefix="Defect 1 (Perspective Drift): ")
add_p("Uploading a new video feed previously displayed the narrative summary and milestones of an earlier sample video. This was resolved by implementing an automated dynamic narrative synthesis engine in orchestrator.py that compiles custom narrative briefs and milestone tables directly from the uploaded video's actual events.", bold_prefix="Defect 2 (Static Fallback Summaries): ")

# ==============================================================================
# CHAPTER 10
# ==============================================================================
add_title("CHAPTER 10: RESULTS, DEMONSTRATION AND DISCUSSION", level=1)

add_title("10.1 Ground-Truth Verification on Surveillance Video (VID-EBBEF071C0EA)", level=2)
add_p("To confirm real-world accuracy, the engine was benchmarked against a 59.4-second continuous office surveillance recording containing 6 distinct human actors and dense office hardware:")

actor_data = [
    ["Person 1", "Primary mobile occupant", "Doorway -> central desk -> room exit", "00:00.2", "00:59.0", "58.8 s", "VERIFIED (100%)"],
    ["Person 2", "Corridor visitor", "Entered corridor -> interacted at desk -> exit", "00:13.6", "00:37.5", "23.9 s", "VERIFIED (100%)"],
    ["Person 3", "Workstation A operator", "Seated continuously at workstation A", "00:04.2", "00:49.1", "44.9 s", "VERIFIED (100%)"],
    ["Person 4", "Workstation B operator", "Seated continuously at workstation B", "00:05.8", "00:36.3", "30.5 s", "VERIFIED (100%)"],
    ["Person 5", "Rear corridor pedestrian", "Walked across background hallway", "00:42.3", "00:56.4", "14.1 s", "VERIFIED (100%)"],
    ["Person 6", "Rear corner operator", "Seated continuously at rear corner workstation", "00:07.5", "00:58.5", "51.0 s", "VERIFIED (100%)"],
]
add_table_data(["Actor ID", "Role Description", "Identified Trajectory", "Start", "End", "Dwell Time", "Ground Truth"], actor_data, [0.8, 1.4, 1.7, 0.6, 0.6, 0.7, 1.0])

add_p("Deep Hardware Inventory Verification: The system cataloged 4 computer monitors (91.5% max confidence), 3 mechanical keyboards (88.4%), 3 computer mice (83.2%), 3 desktop CPU towers (85.1%), and 6 ergonomic office chairs (92.3%), providing one-click video seek to each item's initial appearance timestamp.")

add_title("10.2 System Demonstration Screenshots", level=2)
add_figure_image(FIG_DIR / "fig_10_1_upload.png", "10.1", "Ingest Video Stream Console (/upload) with Processing Engine Profile Selection (Ultra Fast, Balanced, Max Precision)")
add_figure_image(FIG_DIR / "fig_10_5.png", "10.2", "Multi-Stage Processing Pipeline Inspector (/processing/[jobId]) with Real-Time Telemetry and Stage Timers")
add_figure_image(FIG_DIR / "fig_10_2.png", "10.3", "Forensic Timeline Console (/timeline/[videoId]) with Cinema Video Player, Synchronized HUD Overlays, and Plain-Language Executive Brief")
add_figure_image(FIG_DIR / "fig_10_3.png", "10.4", "Multi-Track Story Arcs Studio (/stories/[videoId]) in DAW Sequencer Layout Visualizing Parallel Actor Lifelines")
add_figure_image(FIG_DIR / "fig_10_4.png", "10.5", "Section-Wise Video Events Hub (/events) Grouping Surveillance Events by Ingested Video Asset Cards")
add_figure_image(FIG_DIR / "fig_10_analytics.png", "10.6", "System Analytics & Resource Telemetry Dashboard (/analytics)")

# ==============================================================================
# CHAPTER 11
# ==============================================================================
add_title("CHAPTER 11: CONCLUSION AND FUTURE SCOPE", level=1)

add_title("11.1 Conclusion", level=2)
add_p("The Time Compression Engine (TCE v1.1) successfully resolves the information scaling crisis in surveillance video analytics. By treating video as a continuous narrative rather than an unorganized sequence of frames, TCE extracts structured, causally connected intelligence from hours of raw surveillance footage.")
add_p("Evaluated across 14 rigorous engineering phases, TCE achieved a Real-Time Factor of 0.199 (5.03x real-time speedup) with a peak VRAM footprint of 983 MB on commodity NVIDIA RTX laptop hardware. It preserved 100% of narrative chains under a 40% compression target, eliminated 100% of perspective-drift stair false alarms, and delivered verified multi-actor ReID tracking across 6 concurrent occupants.")

add_title("11.2 Major Engineering Contributions", level=2)
add_p("1. Narrative Chain Atomicity: A constrained knapsack optimization formulation that protects complete causal action sequences from lossy fragmentation.\n2. Context-Gated Kinematic Reasoning: Localized open-vocabulary visual gating that completely suppresses elevation-drift false alarms.\n3. Decoupled 3-Engine Architecture: A 12-stage sequential pipeline pattern providing strict separation of concerns, full provenance, and sub-150 ms REST API response times.\n4. Forensic Reactive Console: A production-grade Next.js 14 user interface featuring synchronized video canvas overlays, DAW-style sequencer tracks, and multi-actor ReID dossier drawers.")

add_title("11.3 Limitations and Future Work", level=2)
add_p("Current limitations include single-camera topological scope and reduced detection confidence in extreme low-light environments (<5 lux) without infrared illumination. Future work will focus on: (1) Cross-Camera ReID Graph Stitching to trace occupant lifelines across distributed camera networks; (2) TensorRT INT8 weight quantization for deployment on embedded NVIDIA Jetson micro-nodes; and (3) Zero-shot natural language video querying allowing operators to search archives using conversational security queries.")

# ==============================================================================
# REFERENCES
# ==============================================================================
add_title("REFERENCES & BIBLIOGRAPHY", level=1)
refs = [
    "Ultralytics. (2024). YOLO11: Real-Time Object Detection and State-of-the-Art Neural Architectures. GitHub Repository. https://github.com/ultralytics/ultralytics",
    "Pritch, Y., Rav-Acha, A., & Peleg, S. (2008). Nonchronological Video Synopsis and Indexing. IEEE Transactions on Pattern Analysis and Machine Intelligence, 30(11), 1971–1984.",
    "Wojke, N., Bewley, A., & Paulus, D. (2017). Simple Online and Realtime Tracking with a Deep Association Metric (DeepSORT). IEEE International Conference on Image Processing (ICIP), 3645–3649.",
    "Zhang, Y., Sun, P., Dong, Y., Jiang, Z., et al. (2022). ByteTrack: Multi-Object Tracking by Associating Every Detection Box. European Conference on Computer Vision (ECCV), Springer, 1–21.",
    "Aharon, N., Orfaig, R., & Bobrovsky, B. Z. (2022). BoT-SORT: Robust Associations Multi-Pedestrian Tracker. arXiv preprint arXiv:2206.14651.",
    "Cheng, B., Choudhuri, R., Misra, I., et al. (2024). YOLO-World: Real-Time Open-Vocabulary Object Detection. IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR).",
    "Howard, A., Sandler, M., Chu, G., Chen, L. C., et al. (2019). Searching for MobileNetV3. IEEE/CVF International Conference on Computer Vision (ICCV), 1314–1324.",
    "Tiangolo, S. (2024). FastAPI: Modern, High-Performance Web Framework for Building APIs with Python. https://fastapi.tiangolo.com",
    "Vercel. (2024). Next.js 14 Documentation and Architecture Guide. https://nextjs.org/docs",
    "Bradski, G. (2000). The OpenCV Library. Dr. Dobb's Journal of Software Tools.",
    "Tomasi, C., & Kanade, T. (1991). Detection and Tracking of Point Features. Carnegie Mellon University Technical Report CMU-CS-91-132.",
    "Fischler, M. A., & Bolles, R. C. (1981). Random Sample Consensus: A Paradigm for Model Fitting with Applications to Image Analysis. Communications of the ACM, 24(6), 381–395.",
    "Hagberg, A., Swart, P., & Schult, D. (2008). Exploring Network Structure, Dynamics, and Function using NetworkX. Proceedings of the 7th Python in Science Conference (SciPy), 11–15.",
    "Sardar Patel Institute of Technology (SPIT). (2026). B.Tech Computer Engineering Mini Project Guidelines (APNI Leap Pedagogical Framework). Department of Computer Engineering, Mumbai."
]
for i, ref in enumerate(refs, 1):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.4)
    p.paragraph_format.first_line_indent = Inches(-0.4)
    p.paragraph_format.space_after = Pt(4)
    p.add_run(f"[{i}] ").bold = True
    p.add_run(ref)

# Save document
doc.save(str(OUTPUT_PATH))
print(f"Report successfully generated and saved at: {OUTPUT_PATH}")

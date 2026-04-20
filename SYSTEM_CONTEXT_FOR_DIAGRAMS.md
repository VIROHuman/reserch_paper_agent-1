# Architectural Context: Research Paper Reference Agent Ecosystem

This document provides a deep-dive into the technical architecture of the **Reference Agent**, intended as high-fidelity context for generating detailed UML (Class and Activity) diagrams.

---

## 1. System Vision & Purpose
The Reference Agent is an **Agentic Research Assistant** that automates the extraction, parsing, and verification of scientific citations. It distinguishes itself from standard reference managers by implementing an **Autonomous Enrichment Loop**, where raw text is iteratively verified against global academic authorities (CrossRef, OpenAlex, Semantic Scholar, DOAJ).

### Core Pillars:
*   **Privacy-First AI**: Local-first processing using Ollama (Llama/Gemma/Phi) ensuring research IP never leaves the user's perimeter.
*   **Hybrid Parsing Engine**: A multi-stage pipeline combining deterministic Regex, probabilistic LLMs, and authoritative API data.
*   **Hardened Security**: A Zero-Trust identity model using JWT and multi-factor SMTP-based OTP.

---

## 2. Component Blueprint

### A. Frontend Layer (Next.js 14 + TypeScript)
*   **Infrastructure Components**:
    *   `AuthProvider`: Centralized React Context managing session lifetime and user identity state.
    *   `AxiosClient`: A hardened HTTP instance with interceptors for stateful JWT attachment and automated 401 (Unauthorized) recovery.
    *   `ProtectedRoute`: A higher-order component (HOC) guarding internal Dashboard routes.
*   **Feature Components**:
    *   `FileUpload`: Handles drag-and-drop ingestion of PDF, DOCX, and DOC files.
    *   `ProcessingStatus`: Real-time tracking of backend jobs (Extraction -> AI Parsing -> API Enrichment).
    *   `ReferenceTable`: Dynamic result view with conflict flagging and JSON/XML export capabilities.

### B. Backend Layer (FastAPI)
*   **API Framework**: Asynchronous REST endpoints with strict Pydantic schema validation.
*   **Job Orchestrator**: A state-management system that tracks long-running document processing jobs via UUIDs.
*   **Identity Service**:
    *   `AuthRouter`: Handles the complexity of 2-stage Registration and Login (Password + OTP).
    *   `EmailService`: SMTP integration for delivering secure, time-sensitive verification codes.
    *   `JWTUtility`: Handles token generation, signing (HS256), and cryptographic verification.

### C. Processing & AI Engine
*   **Extraction Layer**: Pluggable engines for raw text harvesting:
    *   `pdfplumber` & `PyMuPDF (fitz)`: For precise PDF layout analysis and font-embedded text.
    *   `python-docx`: For MS Word document ingestion.
*   **Parsing Layer**:
    *   `SimpleParser`: Regex-based high-speed extraction for standard formats.
    *   `OllamaParser`: Local LLM orchestration for handling messy, non-standard, or broken citations.
*   **Enrichment Layer**: Asynchronous clients for global academic databases:
    *   `CrossRefClient`: Primary authority for DOIs and journal metadata.
    *   `OpenAlexClient`: For abstracts, author verification, and open access data.
    *   `SemanticScholarClient`: For citation counts and paper influence metrics.

### D. DevSecOps Infrastructure
*   **Security Automation**: GitHub Actions running `TruffleHog` (secret scanning) and `Bandit` (SAST).
*   **Quality Assurance**: Automated `ESLint` and `Pytest` suites.
*   **Deployment**: Dockerized services for horizontal scalability.

---

## 3. The Data Journey

### The "Identity Cycle" (User Flow):
1.  **Registration**: User enters details -> SMTP OTP generated -> User verifies email via OTP -> Account activated.
2.  **Authentication**: User provides credentials -> System verifies password -> Sends secondary OTP -> User verifies -> Session (JWT) issued.

### The "Processing Cycle" (Document Flow):
1.  **Ingestion**: File uploaded -> Sanitized (Malware/CDR check) -> Job UUID created.
2.  **Extraction**: PDF/DOCX parsed -> Bibliography section identified -> Raw reference strings extracted.
3.  **Parsing Loop**:
    *   *Step 1*: Regex parsing for "easy" matches.
    *   *Step 2*: Ollama/LLM parsing for "hard" matches.
    *   *Step 3*: Parallel API enrichment queries global sources.
4.  **Verification**: Data from AI and APIs is merged -> Conflicts (e.g., mismatched years) are flagged -> Final structured XML/JSON generated.

---

## 4. UI/UX Aesthetics
*   **Modern Premium**: Glassmorphism effects, vibrant primary accents (#2563eb), and subtle micro-animations (Pulse/Slide/Fade).
*   **Responsive Reliability**: A dashboard that remains functional across mobile, tablet, and desktop environments.

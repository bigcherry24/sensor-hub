# 프로젝트: 소스코드 기반 산출물 자동화 파이프라인 (Platty → docToolchain)

## 배경 및 목표

이 저장소의 **운영 소스코드가 유일한 SSOT(Single Source of Truth)** 이다.
지금까지 수작업으로 작성·관리해 온 기술 문서/업무 산출물을 다음 두 도구를
조합해 자동 생성·자동 현행화(sync)하는 것이 목표다.

1. **Platty** — 소스코드를 정적 분석하여 라우트/데이터모델/API/이벤트/잡/외부
   연동 등을 추출하고, 그 지도를 근거로 LLM이 기술 문서·업무 문서를 작성한다.
2. **docToolchain** — Platty가 뽑아낸 산출물을 arc42 등 공인된 소프트웨어
   아키텍처 문서 템플릿에 맞춰 AsciiDoc으로 정리하고, HTML/PDF/사이트 등
   배포 가능한 최종 형태로 빌드한다.

Claude Code는 이 두 도구를 오케스트레이션하며, **사람의 확인이 필요한
지점에서는 반드시 멈추고 물어본다.**

---

## 절대 원칙 (모든 단계에 공통 적용)

1. **SSOT는 소스코드뿐이다.** 코드로 근거를 추적할 수 없는 내용은 문서에
   넣지 않는다.
2. **의미를 지어내지 않는다.** Platty의 핵심 원칙("보수적 정직함")을 그대로
   계승한다. 두 코드 조각의 연결을 증명할 수 없으면 "미해결(unresolved)"로
   남기고, 그 이유와 함께 최종 문서에도 동일하게 드러낸다. 그럴듯하게
   추측해서 채우지 않는다.
3. **사람 결정 지점에서는 반드시 정지한다.** EPIC 확정, 문서화 대상
   선정, arc42 섹션 매핑 규칙 정의 등은 사람이 최종 승인해야 진행한다.
4. **재생성 가능해야 한다.** 산출물은 사람이 직접 손으로 고치는 대상이
   아니라, 코드가 바뀔 때마다 다시 만들어지는 대상이다. 불가피하게 수작업
   보정이 필요하면 Platty의 `memory` 기능(why/correction/constraint/context)에
   기록해서 재생성 시에도 유실되지 않게 한다.
5. **비용/한도를 인지한다.** LLM 문서화 단계(`generate-docs`, `sync run`)는
   AI 프로바이더 토큰을 소비한다. 큰 저장소를 통째로 돌리기 전에 작은
   범위로 먼저 검증한다.

---

## 사전 확인 체크리스트 (작업 시작 전 반드시 확인)

- [ ] Node.js 버전이 **20~24** 인지 확인 (`node --version`). **Node 25는 미지원.**
- [ ] `git` 사용 가능 여부
- [ ] Platty CLI 설치 여부: `command -v platty` / `platty version`
      (미설치 시 `npm install -g @paradigmshift/platty`)
- [ ] Claude Code용 Platty 플러그인 설치 여부. 없으면 설치 후 **새 세션을
      시작**해야 스킬이 로드된다.
      ```
      claude plugin marketplace add paradigmshift-labs/platty --scope user
      claude plugin install platty@platty --scope user
      ```
- [ ] AI 프로바이더 결정: 이 프로젝트는 **`claude_code`**(로컬 Claude Code
      설치본)를 기본 프로바이더로 사용한다. 별도 API 키가 필요 없다.
      (대안: `claude_api` — `ANTHROPIC_API_KEY` 필요, `codex_cli`)
- [ ] docToolchain: 저장소에 `./dtcw` 래퍼가 있는지 확인 (없으면 최초
      셋업 필요, Gradle 기반이라 Java 런타임 필요)
- [ ] 대상 소스 저장소 경로 확정

---

## 작업 절차

### Phase 0 — 프로젝트 확정
```
platty init
platty project list
platty project create "<프로젝트명>" --description "<설명>"
platty project use "<프로젝트명>"
platty repo add <소스저장소_절대경로>
```
> 저장소 경로 자체는 프로젝트 셀렉터가 아니다. 반드시 `project use`로
> 프로젝트를 먼저 확정한 뒤 `repo add`한다.

### Phase 1 — 정적 분석 (완전 로컬, 코드 실행 없음, AI 비용 없음)
```
platty analyze
platty targets list --status active
```
결과로 나온 API/화면/잡/이벤트 목록을 사람에게 보여주고, 문서화 대상 범위가
맞는지 **확인받은 뒤** 다음 단계로 진행한다.

### Phase 2 — LLM 문서화 (AI 프로바이더 비용 발생)
```
platty generate-docs run --provider claude_code
```
- EPIC 초안 확인을 위해 자동으로 일시 정지되면, 사람에게 EPIC 내용을
  보여주고 승인받은 뒤 진행한다:
  ```
  platty generate-docs confirm-epics --run-id <run-id>
  ```
  (이때 `--provider`는 최초 실행과 **동일하게** 유지)
- 실패한 작업이 있으면:
  ```
  platty generate-docs retry-failed --run-id <run-id>
  platty generate-docs run --provider claude_code
  ```
- 진행 상황/토큰/실패 확인: `platty generate-docs report --run-id <run-id>`

### Phase 3 — SOT 내보내기
```
platty sot export --out <경로>
```
Markdown 트리로 투영된 SOT를 docToolchain의 입력 자료로 사용한다.

### Phase 4 — docToolchain으로 공인 형식 정리
1. Platty 산출물(기술 문서: API/화면/잡/이벤트, 업무 문서: EPIC 등)을
   arc42 문서 구조(빌딩 블록 뷰, 런타임 뷰, 배포 뷰, 품질 시나리오 등)의
   어느 섹션에 대응시킬지 **매핑 규칙을 사람과 함께 1회 정의**한다. 이
   매핑을 자동으로 추론해서 지어내지 않는다 — Platty의 "지어내지 않는다"
   원칙을 그대로 적용한다.
2. 매핑에 따라 Platty SOT 내용을 docToolchain의 AsciiDoc 소스
   (`src/docs/` 등, 프로젝트 설정에 맞춤)에 반영한다.
3. 최종 산출물 빌드:
   ```
   ./dtcw generateHTML     # 단일 HTML
   ./dtcw generatePDF      # PDF
   ./dtcw generateSite     # 마이크로사이트
   ```
   (필요시 `./dtcw exportStructurizr` 등으로 다이어그램 갱신)

### Phase 5 — 현행화(운영 단계, 반복 실행)
코드가 바뀐 뒤 전체를 다시 생성하지 않고 증분 갱신한다:
```
platty sync static-map
platty sync plan
platty sync run --plan-id <plan-id>
platty sync confirm --plan-id <plan-id> --epics-run-id <epics-run-id>
```
그 다음 Phase 4의 docToolchain 빌드를 재실행해 최종 산출물을 갱신한다.
이 Phase 전체를 CI 파이프라인(예: 코드 머지 시 트리거)으로 자동화하는 것이
최종 목표다.

---

## 하지 말아야 할 것

- Platty가 "미해결"로 남긴 증거 간극을 그럴듯한 설명으로 채우지 않는다.
- 저장소 경로를 프로젝트 셀렉터로 쓰지 않는다.
- 자동화/스크립트에서 사람용 텍스트 출력(기본 출력)을 파싱하지 않는다 —
  반드시 `--json`을 붙여 `data`/`nextAction`/`warnings`/`errors`/
  `evidenceRefs` 필드를 읽는다. 사람용 출력 형식은 릴리스마다 바뀔 수 있다.
- EPIC 확인, arc42 매핑 규칙처럼 사람 판단이 필요한 지점을 임의로 넘기지
  않는다.
- 대규모 저장소를 검증 없이 한 번에 전체 실행하지 않는다 (프로바이더
  사용량 한도에 걸려 중단될 수 있음 — 단, 중단돼도 진행 상태는 보존되므로
  이어서 실행 가능).

---

## 참고

- Platty 동작 원리: https://github.com/paradigmshift-labs/platty/blob/main/guide/ko/how-platty-works.md
- Platty 사용 가이드: https://github.com/paradigmshift-labs/platty/blob/main/guide/ko/usage-guide.md
- docToolchain 공식 문서: https://doctoolchain.org/docToolchain/v4.0.x/

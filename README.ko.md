# ChatGPT Web Jjonku Writer

[English](README.md) | [**한국어**](README.ko.md)

> **쫀쿠**는 AI 커뮤니티에서 구독/계정을 부르는 은어입니다. **웹쫀쿠**는 Codex CLI 한도가 아니라 일반 ChatGPT 웹앱 한도를 활용하는 방식을 뜻합니다.

ChatGPT 웹앱이 로컬 저장소를 직접 읽고 수정하고 테스트한 뒤 PR까지 올리게 하는 **OpenAI Secure Tunnel + stdio MCP Git writer**입니다. 범용 셸은 노출하지 않습니다.

> **현재 요금제 조건:** 이 레포가 사용하는 전체 MCP 쓰기·수정 기능은 **ChatGPT Business, Enterprise 또는 Edu**가 필요합니다. 개인 **Pro**는 커스텀 MCP를 read/fetch 용도로만 연결할 수 있고, Plus·Free는 현재 이 전체 쓰기 워크플로를 지원하지 않습니다. 근거: [OpenAI — Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461).
>
> **Luna 정리:** OpenAI 공식 문서상 Luna는 유료 사용자의 일반 Chat에서는 선택할 수 없지만 **Plus·Pro의 Work와 Codex에서는 사용 가능**합니다(Business·Enterprise도 가능). 별도로 커스텀 MCP 정책은 개인 **Pro를 read/fetch 전용**으로 제한하고, 전체 write/modify는 Business·Enterprise·Edu에만 허용합니다. 따라서 Luna+개인 Pro read-only는 배포 대상이지만, Luna+개인 전체 writer는 정책 변경 또는 실제 계정 쓰기 종단시험 전에는 공식 지원으로 주장하지 않습니다.

### 제공 프로필 2종

| 프로필 | 요금제 | 노출 도구 | 검증 상태 |
|---|---|---|---|
| 전체 writer | Business / Enterprise / Edu | 읽기·쓰기·검사·커밋·PR·merge 9종 | 종단 검증 완료 |
| 개인 read-only | Pro | `repo_read`, `repo_search`, `git_diff` 3종 | 코드 검증 완료, Pro 계정 종단 미검증 |

개인 프로필은 fail-closed입니다. 쓰기 도구를 discovery에서 숨기고 직접 호출해도 서버가 거부합니다. Plus·Free·Go는 현재 OpenAI 공식 커스텀 MCP 지원 범위 밖입니다.

```text
웹 ChatGPT → OpenAI Secure Tunnel → 내 컴퓨터의 tunnel-client
            → stdio MCP Git writer → 지정 저장소 → chatgpt/* 브랜치 → PR
```

## 왜 쓰나요?

Codex CLI와 `openai-codex` OAuth 경로는 Codex 사용량 풀을 소비합니다. 반면 OpenAI 공식 요금 문서는 일반 ChatGPT 사용량은 Codex 사용량에 포함되지 않는다고 설명합니다.

- 공식 문서: [ChatGPT Work and Codex share usage / Regular Chat usage isn't included](https://learn.chatgpt.com/docs/pricing)
- 실제 측정: 동일 계정에서 Codex가 `usage_limit_reached (429)`인 동안 웹 ChatGPT의 일반 대화와 코딩 요청은 정상 응답

따라서 Codex 한도가 끝나도 chatgpt.com은 계속 사용할 수 있습니다. 이 프로젝트는 웹에서 받은 코드를 사람이 복사·붙여넣지 않고 **실제 저장소에 직접 반영**하게 합니다.

## 무엇이 유용한가요?

1. **사용량 풀 확장** — Codex 풀과 웹 채팅 풀을 별도로 활용합니다.
2. **휴대폰 코딩** — 폰의 ChatGPT에서 요청해도 내 컴퓨터 저장소에 PR이 만들어집니다.
3. **복사·붙여넣기 제거** — 웹 GPT가 실제 파일을 읽고 수정하고 설정된 검사를 실행합니다.
4. **검토 가능한 변경** — 모든 쓰기 작업은 `chatgpt/*` 브랜치와 PR을 거칩니다.
5. **공개 포트 없음** — `tunnel-client`가 OpenAI로 outbound 연결하므로 ngrok 같은 공개 터널이 필요 없습니다.

## 반드시 알아야 할 한계

1. **로컬 에이전트의 모델 폴백이 아닙니다.** Claude Code, Codex CLI, Hermes, OpenClaw는 API의 구조화된 tool call로 도구를 실행합니다. 웹 ChatGPT는 일반 대화 응답을 반환하므로 기존 에이전트의 fallback chain에 넣고 툴콜까지 유지할 수 없습니다.
2. **웹 GPT와 로컬 에이전트는 서로 대화하지 못합니다.** 공유하는 것은 브랜치·커밋·PR뿐입니다.
3. **Secure Tunnel 사용 권한이 필요합니다.** Platform 조직과 ChatGPT workspace를 연결해 터널을 만들 수 있어야 합니다.
4. **내 컴퓨터와 데몬이 켜져 있어야 합니다.** 컴퓨터가 자거나 데몬이 죽으면 웹에서 도구가 사라집니다.
5. **writer 하나는 저장소 하나만 담당합니다.** 여러 저장소는 writer/터널을 별도로 운영하는 것이 안전합니다.
6. **AI의 잘못된 패치는 여전히 가능합니다.** branch protection, required checks, 사람의 PR 리뷰가 핵심 안전장치입니다.
7. **구독 및 서비스 약관 확인 책임은 운영자에게 있습니다.**

## 제공 도구

- `repo_read`: 파일 읽기
- `repo_search`: `git grep`
- `branch_start`: 기준 브랜치에서 `chatgpt/<name>` 생성
- `repo_write`: 파일 전체 쓰기 (`chatgpt/*`에서만)
- `git_diff`: 변경사항 보기
- `run_check`: 설정에 등록된 검사만 실행
- `commit_push`: 커밋하고 작업 브랜치 push
- `pr_create`: PR 생성/재사용
- `pr_merge`: required checks 통과 후 squash auto-merge

**셸 도구와 임의 명령 실행은 없습니다.**

## 보안 경계

| 통제 | 강제 방식 |
|---|---|
| 저장소 밖 접근 금지 | 모든 경로가 `repo_root` 아래인지 확인 |
| 보호 파일 금지 | `.github/workflows`, `.git/config` 등을 `deny_paths`로 차단 |
| 작업 브랜치 강제 | `chatgpt/*`가 아니면 쓰기·커밋 거부 |
| force-push 금지 | `git push`만 사용, `--force` 없음 |
| 임의 셸 금지 | `run_check`는 설정된 명령 배열만 실행 |
| 자기 수정 금지 | writer와 검증 파일을 대상 저장소 밖에 설치 |
| 비밀값 보호 | 터널 키를 저장소 밖 `tunnel.env`에 mode 600으로 저장 |

```bash
node selfcheck.mjs
# ALL PASS (7 assertions, 5 guards)

node e2e-test.mjs
# E2E PASS: branch -> write -> diff -> check -> commit -> push, main untouched
```

## 설치

준비물: Node 18+, Git, GitHub CLI `gh` 로그인, remote가 있는 대상 저장소.

```bash
git clone https://github.com/kims6305-bjk/chatgpt-web-jjonku-writer
cd chatgpt-web-jjonku-writer
./install.sh
```

### 1. OpenAI 터널 생성

[Platform → Organization → Tunnels](https://platform.openai.com/settings/organization/tunnels)에서 터널을 만듭니다.

- Name/Description 입력
- Organization 선택
- **ChatGPT workspaces를 반드시 선택** — 비워두면 ChatGPT에서 `No available tunnels`
- `tunnel_...` ID 복사

### 2. Runtime API key 생성

[Platform → Organization → API keys](https://platform.openai.com/settings/organization/api-keys)에서 새 secret key를 만듭니다.

- Permissions: `Restricted`
- `Tunnels`: **Read + Use**만
- Admin key는 UI로 터널을 만들었다면 필요 없습니다.

### 3. writer 설정

```bash
cd ~/.local/share/webgpt-git-writer

# Business / Enterprise / Edu: 전체 read/write 프로필
cp writer.config.example.json writer.config.json
# writer.config.json에서 repo_root / base_branch / deny_paths / checks 수정
node selfcheck.mjs   # ALL PASS 확인

# 개인 Pro: read/fetch 전용(위 3줄 대신 사용)
# cp writer.config.personal-pro.example.json writer.config.json
# repo_root / base_branch / deny_paths 수정
# node selfcheck-readonly.mjs   # READ-ONLY PASS 확인

./set-key.sh
```

### 4. 터널 프로필과 상시 서비스

```bash
./setup-tunnel.sh       # doctor의 RESULT ok 확인
./install-service.sh    # macOS launchd / Linux systemd --user
curl -fsS http://127.0.0.1:8791/readyz
# ready
```

### 5. ChatGPT 커넥터 연결

데몬이 실행 중일 때 [ChatGPT Connectors](https://chatgpt.com/#settings/Connectors)에서:

1. 검색이 아니라 **⊕ 버튼**으로 커스텀 커넥터 추가
2. Connection: **Tunnel**
3. 생성한 터널 선택
4. Authentication: **No authentication**
5. 검토되지 않은 서버 경고 확인 후 Connect

stdio MCP는 OAuth 메타데이터를 노출하지 않으므로 OAuth를 선택하면 연결이 실패합니다.

## 사용법

새 ChatGPT 대화에서 `git-writer` 커넥터를 켜고 자연어로 요청합니다.

- `AGENTS.md를 읽어줘`
- `chatgpt/fix-login 브랜치를 만들고 빈 비밀번호를 거부하도록 수정한 뒤 테스트하고 PR 올려줘`
- `전체 diff 보여줘`
- `required checks가 통과하면 squash merge해줘`

## 종단 검증

ChatGPT가 “읽었다”고 말한 것만 믿지 마세요. 실제 호출 로그와 원본을 대조합니다.

```bash
~/.local/share/webgpt-git-writer/verify.sh

grep -c 'forwarded command to MCP server' \
  ~/.local/share/webgpt-git-writer/tunnel.log
```

웹 화면에 출력된 파일 내용과 내 컴퓨터의 실제 파일 내용이 일치해야 완료입니다.

## 에이전트용 범용 스킬

- `skills/hermes/.../SKILL.md`: Hermes, OpenClaw, Claude Code용
- `skills/codex/AGENTS.md`: Codex CLI용
- `skills/generic/PLAYBOOK.md`: 기타 에이전트용 일반 런북
- `skills/AGENTS.snippet.md`: 웹 GPT가 따라야 할 저장소 계약문

자세한 장애 해결표와 설계 설명은 [영문 README](README.md)에 함께 들어 있습니다.

## 라이선스

MIT

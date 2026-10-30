#!/bin/bash
# bdpan OOB 登录脚本
# 用于非 GUI 环境下的手动授权登录

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 解析参数
SKIP_CONFIRM="no"
SHOW_WELCOME="yes"
while [[ $# -gt 0 ]]; do
    case $1 in
        --yes|-y)
            SKIP_CONFIRM="yes"
            shift
            ;;
        --continue-task|--quiet|--no-welcome)
            # 被原任务自动调用时，登录成功后静默返回，让调用方继续原任务。
            SHOW_WELCOME="no"
            shift
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --yes, -y    跳过安全确认（自动化场景）"
            echo "  --continue-task  登录成功后不输出欢迎语，供原任务继续执行"
            echo "  --help       显示帮助信息"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

manual_login_hint() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    echo ""
    echo "请重新执行手动授权登录后再试："
    echo "bash \"${script_dir}/scripts/login.sh\""
}

fail_login() {
    local reason="$1"
    if [ -z "$reason" ]; then
        reason="CLI 未返回具体失败原因"
    fi
    log_error "登录失败：${reason}"
    manual_login_hint
    exit 1
}

print_capability_examples() {
    echo "- 帮我找一份周末京津冀旅行攻略，整理好后存到网盘"
    echo "- 把刚生成的简历和作品集上传到网盘"
    echo "- 把朋友分享的照片转存到我的网盘"
    echo "- 找出网盘里去年的体检报告"
    echo "- 备份我的 Agent 记忆，方便以后恢复"
}

print_success_welcome() {
    echo ""
    echo "登录成功，现在可以使用百度网盘了。"
    echo ""
    echo "你可以直接说："
    print_capability_examples
}

print_already_logged_welcome() {
    echo ""
    echo "你已登录百度网盘，无需重复授权。"
    echo ""
    echo "现在可以直接说："
    print_capability_examples
}

# 检查 bdpan 是否已安装
if ! command -v bdpan &> /dev/null; then
    log_error "bdpan 未安装，请先运行: bash scripts/install.sh"
    exit 1
fi

# 检查当前登录状态
log_info "检查登录状态..."

# 获取 bdpan 版本
BDPAN_VERSION=$(bdpan version 2>/dev/null | head -1 || echo "unknown")

if bdpan whoami 2>/dev/null | grep -q "已登录"; then
    # 用户主动登录时给出可执行的场景提示；原任务前置登录保持静默。
    if [ "$SHOW_WELCOME" = "yes" ]; then
        print_already_logged_welcome
    fi
    exit 0
fi

log_info "未登录，开始 OOB 授权流程..."

# 首次安全登录依赖三个非交互参数，进入授权流程前一次性完成能力检查
LOGIN_HELP=$(bdpan login --help 2>&1 || true)
MISSING_FLAGS=""
for required_flag in --get-auth-url --set-code-stdin --accept-disclaimer; do
    if ! printf '%s\n' "$LOGIN_HELP" | grep -Fq -- "$required_flag"; then
        MISSING_FLAGS="${MISSING_FLAGS} ${required_flag}"
    fi
done

if [ -n "$MISSING_FLAGS" ]; then
    log_error "当前 bdpan 版本不支持首次安全登录所需参数:${MISSING_FLAGS}"
    log_error "当前 bdpan 版本: ${BDPAN_VERSION}"
    log_error "请先升级后重试: bash scripts/install.sh --force"
    exit 1
fi

# 安全免责声明
echo ""
echo -e "${RED}┌──────────────────────────────────────────────────────────────┐${NC}"
echo -e "${RED}│              ⚠️  baidu drive 安全须知 & 免责声明                │${NC}"
echo -e "${RED}├──────────────────────────────────────────────────────────────┤${NC}"
echo -e "${RED}│${NC} 1. 请备份网盘重要数据，谨慎操作。                            ${RED}│${NC}"
echo -e "${RED}│${NC}    请务必【备份】网盘重要数据。                               ${RED}│${NC}"
echo -e "${RED}│${NC} 2. [行为负责] AI Agent 行为具有不可预测性，请实时             ${RED}│${NC}"
echo -e "${RED}│${NC}    【人工审核】指令执行过程，对执行后果负责。                  ${RED}│${NC}"
echo -e "${RED}│${NC} 3. [安全提醒] 严禁在他人、公用或不可信的环境中                ${RED}│${NC}"
echo -e "${RED}│${NC}    扫码授权，以免网盘数据被窃取！                              ${RED}│${NC}"
echo -e "${RED}│${NC}    在公共环境使用完毕后，请务必执行                             ${RED}│${NC}"
echo -e "${RED}│${NC}    【bdpan logout】 彻底清除授权。                             ${RED}│${NC}"
echo -e "${RED}│${NC} 4. [严禁泄露] 请严格保护配置文件与 Token，                    ${RED}│${NC}"
echo -e "${RED}│${NC}    切勿在公开仓库或对话中暴露！                                ${RED}│${NC}"
echo -e "${RED}├──────────────────────────────────────────────────────────────┤${NC}"
echo -e "${RED}│${NC} 使用本工具即代表您已阅读并认可上述条款。数据安全，人人有责。  ${RED}│${NC}"
echo -e "${RED}└──────────────────────────────────────────────────────────────┘${NC}"
echo ""

# 用户确认
if [ "$SKIP_CONFIRM" = "yes" ]; then
    log_info "自动模式，跳过安全确认"
else
    echo -n -e "${YELLOW}已阅读上述安全须知，确认继续登录? [y/N] ${NC}"
    read -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "已取消登录"
        exit 0
    fi
fi

# 获取授权链接
log_info "正在获取授权链接..."

# 成功路径只取 stdout：CLI 在 exit 0 时也可能向 stderr 输出版本/升级提示，
# 若用 2>&1 合并会让 AUTH_URL 变成「URL + 噪声」的混合串，后续纯文本行和
# Markdown 链接都会损坏，Agent 抓到的链接无法跳转。
# 失败路径单独从临时文件读取 stderr 作为错误原因。
AUTH_ERR_FILE="$(mktemp "${TMPDIR:-/tmp}/bdpan-auth-err-XXXXXX")"
if ! AUTH_URL=$(bdpan login --get-auth-url --accept-disclaimer 2>"$AUTH_ERR_FILE"); then
    AUTH_ERROR="$(cat "$AUTH_ERR_FILE" 2>/dev/null || true)"
    rm -f "$AUTH_ERR_FILE"
    fail_login "获取授权链接失败：${AUTH_ERROR}"
fi
rm -f "$AUTH_ERR_FILE"

if [ -z "$AUTH_URL" ]; then
    fail_login "获取授权链接失败：CLI 返回了空授权链接"
fi

# 显示授权链接
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}请在浏览器中打开以下链接完成授权:${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
# 纯文本单独一行输出，不附带任何 ANSI/OSC 转义序列。
# 无论是真实终端、日志采集，还是 AI Agent（如小艺 claw 等）抓取 stdout 文本
# 再转发展示给用户，都能拿到一个完整、干净、可直接复制/点击的 URL。
# 注意：此前版本使用 OSC 8 超链接转义序列（\e]8;;URL\e\\显示文本\e]8;;\e\\）
# 在同一行内嵌入了两次 URL，在非真实终端环境（如部分 Agent 的输出解析逻辑）
# 下容易被截断或错误拼接，导致用户拿到的链接不可用。
echo "${AUTH_URL}"
echo ""
# 提供给 AI Agent 的 Markdown 格式，便于 Agent 直接抓取并放到代码块外
echo -e "${YELLOW}Agent请提取以下Markdown格式回复给用户(需放在代码块外):${NC}"
echo "[👉 点击此处打开授权页面](${AUTH_URL})"
echo ""
# 仅在真实交互式终端下，额外附加 OSC 8 可点击版本作为增强体验
# （支持 iTerm2、VS Code Terminal、Wezterm、GNOME Terminal、Windows Terminal 等）。
# 当 stdout 被管道/重定向或被 Agent 捕获时 [ -t 1 ] 为 false，不会输出该转义
# 序列，从而避免被非终端场景的文本解析逻辑误处理。
if [ -t 1 ]; then
    echo -e "\033]8;;${AUTH_URL}\033\\${YELLOW}👆 点击此处直接打开授权页面（如终端支持）${NC}\033]8;;\033\\"
    echo ""
fi
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}提示:${NC}"
echo -e "${YELLOW}1. 可直接复制上方链接到浏览器打开（支持的终端也可直接点击）${NC}"
echo -e "${YELLOW}2. 链接有效期为 10 分钟${NC}"
echo -e "${YELLOW}3. 授权成功后，浏览器会显示一个 32 位授权码${NC}"
echo -e "${YELLOW}4. 请复制授权码并粘贴到下方${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 提示用户输入授权码
echo -n "请输入浏览器中显示的授权码 (32 位十六进制字符): "
read -r -s AUTH_CODE
echo

if [ -z "$AUTH_CODE" ]; then
    fail_login "授权码不能为空"
fi

# 校验授权码格式：32 位十六进制字符，不通过子进程传递或输出原值
if [[ ! "$AUTH_CODE" =~ ^[a-fA-F0-9]{32}$ ]]; then
    fail_login "授权码格式不正确（应为 32 位十六进制字符），请确认复制完整"
fi

# 使用授权码完成登录
log_info "正在使用授权码完成登录..."

# 通过 stdin 传递授权码，避免在进程参数中泄露
if ! LOGIN_ERROR=$(printf '%s\n' "$AUTH_CODE" | bdpan login --set-code-stdin --accept-disclaimer 2>&1); then
    LOGIN_ERROR=${LOGIN_ERROR//$AUTH_CODE/[授权码已隐藏]}
    unset AUTH_CODE
    fail_login "$LOGIN_ERROR"
    unset LOGIN_ERROR
fi
unset LOGIN_ERROR

# 立即清除内存中的授权码
unset AUTH_CODE

# 验证登录，并区分命令失败与未登录状态，保留 CLI 实际原因。
WHOAMI_OUTPUT=""
if WHOAMI_OUTPUT=$(bdpan whoami 2>&1) && printf '%s\n' "$WHOAMI_OUTPUT" | grep -q "已登录"; then
    if [ "$SHOW_WELCOME" = "yes" ]; then
        log_info "✓ 登录成功！"
        print_success_welcome
    fi
else
    fail_login "$WHOAMI_OUTPUT"
fi
unset WHOAMI_OUTPUT

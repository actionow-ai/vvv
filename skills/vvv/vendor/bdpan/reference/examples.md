# 使用示例

本文档包含 baidu drive 的详细使用示例。

---

## 上传并分享

### 示例 1: 上传并分享单个文件

```
用户: 帮我上传并分享 ./report.pdf
AI: [执行 bdpan upload ./report.pdf report.pdf]
    [执行 bdpan share report.pdf]

    上传并分享成功！
    链接: <百度网盘分享链接>
    提取码: abcd
    有效期: 7 天
```

### 示例 2: 上传并分享文件夹

```
用户: 把 ./project 文件夹上传并分享
AI: [执行 bdpan upload ./project/ project/]
    [执行 bdpan share project]

    文件夹上传并分享成功！
    链接: <百度网盘分享链接>
    提取码: efgh
    有效期: 7 天
```

### 示例 3: 上传到子目录

```
用户: 上传 ./data.tar.gz 到 backup 目录并分享
AI: [执行 bdpan upload ./data.tar.gz backup/data.tar.gz]
    [执行 bdpan share backup/data.tar.gz]

    上传并分享成功！
    链接: <百度网盘分享链接>
    提取码: ijkl
    有效期: 7 天
```

---

## 下载文件

### 示例 4: 下载单个文件

```
用户: 从网盘下载 report.pdf
AI: [执行 bdpan download report.pdf ./report.pdf]

    正在下载 report.pdf → ./report.pdf ...
    ✓ 下载成功
```

### 示例 5: 下载文件夹

```
用户: 把 backup 文件夹下载到本地
AI: [执行 bdpan download backup/ ./backup/]

    正在下载 backup/ → ./backup/ ...
    ✓ 下载成功
```

---

## 文件列表

### 示例 6: 查看已上传文件

```
用户: 查看我上传了哪些文件
AI: [执行 bdpan ls --json]

    # 逐项原样输出 JSON 中的 return_markdown（CLI 已渲染好的 [点击查看](链接)）
    #   该字段缺失时才用 return_url 自行渲染，文案统一“点击查看”
    #   链接地址必须原样使用对应项的 return_url，禁止改写或截断
    #   （下表“该项 return_url”是占位说明，不是可用地址；实际回复必须替换为 CLI 返回的完整 URL）
    | 文件名     | 类型   | 大小   | 查看 |
    |------------|--------|--------|------|
    | backup     | 文件夹 | —      | [点击查看](该项 return_url) |
    | report.pdf | 文件   | 1.5 MB | [点击查看](该项 return_url) |
    | config.yaml| 文件   | 256 KB | [点击查看](该项 return_url) |

    共 3 项
```

### 示例 7: 查看子目录

```
用户: 查看 backup 目录下的文件
AI: [执行 bdpan ls backup --json]

    | 文件名                 | 类型 | 大小   | 查看 |
    |------------------------|------|--------|------|
    | data-2026-02-19.tar.gz | 文件 | 2.1 GB | [点击查看](该项 return_url) |
    | data-2026-02-18.tar.gz | 文件 | 1.8 GB | [点击查看](该项 return_url) |

    共 2 项
```

---

## JSON 输出（用于脚本）

### 示例 8: JSON 格式文件列表

```
用户: 列出所有文件名（JSON 格式）
AI: [执行 bdpan ls --json]

    输出:
    [
      {
        "fs_id": 123456789,
        "fsid": "123456789",
        "server_filename": "report.pdf",
        "path": "/apps/bdpan/report.pdf",
        "size": 1536000,
        "isdir": false,
        "server_mtime": "2026-02-25T15:20:00Z"
      },
      {
        "fs_id": 987654321,
        "fsid": "987654321",
        "server_filename": "backup",
        "path": "/apps/bdpan/backup",
        "size": 0,
        "isdir": true,
        "server_mtime": "2026-02-20T10:30:00Z"
      }
    ]
```

### 示例 9: 使用 jq 处理输出

```bash
# 提取所有文件名
bdpan ls --json | jq -r '.[].server_filename'

# 提取文件 ID（必须使用字符串字段，避免大整数精度丢失）
bdpan ls --json | jq -r '.[].fsid'

# 只列出文件（排除目录）
bdpan ls --json | jq '.[] | select(.isdir == false)'

# 按大小排序
bdpan ls --json | jq 'sort_by(.size) | reverse'

# 检查文件是否存在
bdpan ls --json | jq -e '.[] | select(.server_filename == "target.txt")'
```

---

## 认证流程

### 示例 10: 登录（统一使用 login.sh 脚本）

> 登录安全约束详见 [SKILL.md](../SKILL.md) 的「安全约束」章节。

```
用户: 帮我登录百度网盘
AI: [执行 bash ${CLAUDE_SKILL_DIR}/scripts/login.sh]

    [展示安全免责声明]
    已阅读上述安全须知，确认继续登录? [y/N]

用户: y
AI: 正在获取授权链接...

    请在浏览器中打开以下链接完成授权:
    https://openapi.baidu.com/oauth/2.0/authorize?...

    授权成功后，浏览器会显示授权码，请复制并粘贴到这里:
    [等待用户输入...]

用户: [粘贴授权码] ca0ee3070f75d0246357e5c74d525bda
AI: [处理授权码]

    登录成功，现在可以使用百度网盘了。

    你可以直接说：
    - 帮我找一份周末京津冀旅行攻略，整理好后存到网盘
    - 把刚生成的简历和作品集上传到网盘
    - 把朋友分享的照片转存到我的网盘
    - 找出网盘里去年的体检报告
    - 备份我的 Agent 记忆，方便以后恢复
```

### 示例 10a: 原任务触发登录

```
用户: 把刚生成的简历上传到网盘
AI: [发现未登录，执行 bash ${CLAUDE_SKILL_DIR}/scripts/login.sh --continue-task]
AI: [用户完成授权后，继续执行原上传任务，不重复输出登录欢迎语]
```

### 示例 10b: 已有登录态时主动进入登录

```
用户: 帮我登录百度网盘
AI: [执行 bash ${CLAUDE_SKILL_DIR}/scripts/login.sh]

    你已登录百度网盘，无需重复授权。

    现在可以直接说：
    - 帮我找一份周末京津冀旅行攻略，整理好后存到网盘
    - 把刚生成的简历和作品集上传到网盘
    - 把朋友分享的照片转存到我的网盘
    - 找出网盘里去年的体检报告
    - 备份我的 Agent 记忆，方便以后恢复
```

---

## 转存分享文件到网盘

### 示例 15a: 转存无码公开分享链接

```
用户: 帮我把这个无码分享链接转存到网盘 <百度网盘分享链接>
AI: [执行 bdpan transfer "<百度网盘分享链接>"]

    ✓ 转存成功！
    文件已保存到：我的应用数据/bdpan/学习资料/课程讲义.pdf
```

### 示例 15: 转存分享链接（提取码在链接中）

```
用户: 帮我把这个链接转存到网盘 <百度网盘分享链接>?pwd=abcd
AI: [执行 bdpan transfer "<百度网盘分享链接>?pwd=abcd"]

    ✓ 转存成功！
    文件已保存到：我的应用数据/bdpan/学习资料/课程讲义.pdf
```

### 示例 16: 转存到指定目录

```
用户: 把 <百度网盘分享链接> 转存到 shared 目录，提取码是 efgh
AI: [执行 bdpan transfer "<百度网盘分享链接>" -p efgh -d shared/]

    ✓ 转存成功！
    文件已保存到：我的应用数据/bdpan/shared/课程讲义.pdf
```

### 示例 17: 转存并查看结果（JSON）

```bash
bdpan transfer "<百度网盘分享链接>?pwd=abcd" --json
# 输出:
# {
#   "saved_path": "我的应用数据/bdpan/shared/",
#   "count": 1,
#   "files": [
#     {
#       "name": "课程讲义.pdf",
#       "path": "/apps/bdpan/shared/课程讲义.pdf",
#       "saved_path": "我的应用数据/bdpan/shared/课程讲义.pdf",
#       "return_url": "https://pan.baidu.com/union/spirit/launch?...",
#       "return_target_type": "directory",
#       "return_hint": "点击查看",
#       "return_markdown": "[点击查看](该项 return_url)",
#       "size": 47104,
#       "is_dir": false
#     }
#   ]
# }
```

回端链接的文件目标（`target=file`）和目录目标（`target=dir`）都由网盘主端判断能否预览，因此展示文案统一为“点击查看”，以 CLI 返回的 `return_hint` 为准。Agent 应优先原样输出 CLI 预渲染的 `return_markdown`；Skill 不自行拼接或改写回端 URL，也不按扩展名判断可预览性。

---

## 搜索文件

### 示例 18: 搜索文件

```
用户: 在网盘里搜索 report
AI: [执行 bdpan search report --json]

    找到 3 个结果（第 1 页，共 1 页）

    | # | 名称              | 类型   | 大小    | 查看 |
    |---|-------------------|--------|---------|------|
    | 1 | report.pdf        | 文档   | 1.5 MB  | [点击查看](该项 return_url) |
    | 2 | report-draft.docx | 文档   | 256 KB  | [点击查看](该项 return_url) |
    | 3 | report-backup     | 文件夹 | —       | [点击查看](该项 return_url) |
```

### 示例 19: 按类型搜索

```
用户: 搜索网盘里所有的图片文件
AI: [执行 bdpan search "" --category 3 --no-dir --json]

    找到 5 个结果（第 1 页，共 1 页）

    | # | 名称          | 类型 | 大小   | 查看 |
    |---|---------------|------|--------|------|
    | 1 | photo.jpg     | 图片 | 3.2 MB | [点击查看](该项 return_url) |
    | 2 | screenshot.png | 图片 | 1.1 MB | [点击查看](该项 return_url) |
    | … | …             | …    | …      | 每项均按 `return_url` 提供链接 |
```

---

## 文件管理（移动/复制/重命名/创建文件夹）

### 示例 20: 移动文件

```
用户: 把网盘里的 report.pdf 移动到 backup 目录
AI: [执行 bdpan mv report.pdf backup]

    已移动 report.pdf -> backup
```

### 示例 21: 复制文件

```
用户: 复制 report.pdf 到 archive 目录
AI: [执行 bdpan cp report.pdf archive]

    已复制 report.pdf -> archive
```

### 示例 22: 重命名文件

```
用户: 把 draft.pdf 重命名为 final-report.pdf
AI: [执行 bdpan rename draft.pdf final-report.pdf]

    已重命名 draft.pdf -> final-report.pdf
```

### 示例 23: 创建文件夹

```
用户: 在网盘里创建一个 projects 文件夹
AI: [执行 bdpan mkdir projects]

    已创建文件夹: projects
```

### 示例 24: 组合操作——创建目录并移动文件

```
用户: 帮我在网盘里创建一个 archive/2026 目录，然后把 old-report.pdf 移动过去
AI: [执行 bdpan mkdir archive/2026]
    已创建文件夹: archive/2026

    [执行 bdpan mv old-report.pdf archive/2026]
    已移动 old-report.pdf -> archive/2026
```

---

## 高级用法

### 示例 12: 批量上传

```bash
# 上传当前目录所有 PDF 文件
for f in *.pdf; do
  bdpan upload "$f" "documents/$f"
done

# 上传并记录结果
for f in *.pdf; do
  echo "上传 $f..."
  bdpan upload "$f" "documents/$f" --json | jq '.'
done
```

### 示例 13: 自动备份脚本

```bash
#!/bin/bash
# 每日备份脚本

DATE=$(date +%Y-%m-%d)
BACKUP_FILE="backup-${DATE}.tar.gz"

# 打包
tar -czf "/tmp/${BACKUP_FILE}" ~/important-data/

# 上传
bdpan upload "/tmp/${BACKUP_FILE}" "backup/${BACKUP_FILE}"

# 清理
rm "/tmp/${BACKUP_FILE}"

echo "备份完成: ${BACKUP_FILE}"
```

### 示例 14: 检查上传状态

```bash
# 检查文件是否已上传
check_uploaded() {
  local file=$1
  bdpan ls --json | jq -e ".[] | select(.server_filename == \"${file}\")" > /dev/null
}

if check_uploaded "report.pdf"; then
  echo "文件已存在"
else
  echo "文件不存在，开始上传..."
  bdpan upload ./report.pdf report.pdf
fi
```

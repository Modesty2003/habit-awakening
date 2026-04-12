# ⚡ 觉醒系统 (Awakening System)

> 专属你的热血习惯追踪系统 — 排球少年风格 × 小说系统面板 × 数学模型驱动

---

## 功能一览

| 功能 | 说明 |
|------|------|
| 角色系统 | 等级 + EXP + 四维属性（智慧/体能/专注/意志） |
| 每日任务 | 四类习惯打卡，连击加成 EXP |
| 势头仪表盘 | 指数移动平均（EMA α=0.35）计算近14天势头 |
| 坚持指数 | 滚动30天完成率 |
| BOSS战 | 每周完成率≥80%即告捷，BOSS名称每周随机 |
| 系统消息 | 根据数学模型输出排球少年风格鼓励语 |
| 成就系统 | 15个成就，解锁即弹窗庆祝 |
| 战况报告 | 30天趋势柱状图 + 四维属性雷达图 |

---

## 快速开始

### 方式一：全功能版（推荐）

```bash
# 1. 进入项目目录
cd ~/habit-awakening

# 2. 安装依赖
pip3 install -r requirements.txt

# 3. 启动（自动打开浏览器）
./start.sh
# 或 Windows:
# start.bat
```

访问 http://127.0.0.1:7788

### 方式二：Lite 版（无需服务器）

直接双击打开 `lite/index.html`，或拖入浏览器。

数据保存在浏览器 localStorage，可加入浏览器书签或添加到桌面快捷方式。

---

## 数学模型说明

### EXP 等级曲线
```
等级阈值(n) = 250 × (n-1)^1.65
```
- Lv.2: 250 EXP
- Lv.5: ~1700 EXP  
- Lv.10: ~7000 EXP

### 连击加成
```
EXP × (1 + min(连击天数 × 0.08, 1.5))
最高 2.5 倍 EXP
```

### 势头指数（EMA）
```
EMA_today = 0.35 × 今日完成率 + 0.65 × EMA_yesterday
势头 = EMA × 100
```

### 坚持指数
```
(过去30天内完成次数) / (习惯数 × 30) × 100%
```

### 每周BOSS战
```
本周完成次数 / (习惯数 × 已过天数) ≥ 80% → 胜利
```

---

## 上传到 GitHub

```bash
cd ~/habit-awakening
git init
git add .
git commit -m "init: 觉醒系统 v1.0"
git remote add origin https://github.com/你的用户名/habit-awakening.git
git push -u origin main
```

---

## 打包为 macOS App（可选）

```bash
pip3 install pyinstaller
pyinstaller --onefile --windowed --name "觉醒系统" launcher.py
# 输出在 dist/ 目录
```

---

## 部署到线上（Vercel + Railway）

- **Lite 版**：直接将 `lite/index.html` 部署到 Vercel / GitHub Pages
- **全功能版**：后端部署到 Railway，前端可通过环境变量指向 API 地址

---

## 项目结构

```
habit-awakening/
├── backend/
│   ├── main.py          # FastAPI 路由
│   ├── database.py      # SQLite 初始化
│   ├── analytics.py     # 数学模型（EMA/连击/等级）
│   └── achievements.py  # 成就检测
├── frontend/
│   └── index.html       # 全功能前端（排球少年风格）
├── lite/
│   └── index.html       # 单文件 Lite 版（localStorage）
├── data/                # SQLite 数据库（运行时自动创建）
├── launcher.py          # 桌面启动器
├── start.sh             # macOS/Linux 启动脚本
├── start.bat            # Windows 启动脚本
└── requirements.txt
```

---

*永不放弃，一步一步。*

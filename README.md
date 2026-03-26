# ctrip_international_flight_crawler
携程国际版航班爬虫与智能分析工具，支持自动化爬取、中转筛选、高性价比航班智能推荐。
## 项目简介
本项目包含两个核心模块：
1. **爬虫模块** (`ctrip_flights_scraper_V1.py`)：基于 Selenium 的携程国际版航班数据爬取工具
2. **分析模块** (`analyze.py`)：数据整合与智能筛选工具，自动推荐高性价比航班

## 功能特性

### 🕷️ 爬虫模块 (`ctrip_flights_scraper_V4.1.py`)

- **自动化爬取**：支持多城市、多日期批量爬取
- **智能登录**：支持 Cookie 复用、账号密码登录、短信验证码处理
- **页面原生筛选**：直接操作页面筛选栏，筛选上海中转航班
- **低价优先排序**：自动点击"低价优先"，保证获取最便宜的航班
- **容错机制**：完善的错误重试、超时处理、截图调试功能
- **反爬策略**：隐身模式、自动化特征隐藏、随机延迟

### 📊 分析模块 (`analyze.py`)

- **数据整合**：自动遍历并合并所有爬取的 CSV 文件
- **智能筛选**：
  - 基础条件：上海中转
  - 时间偏好：15:00-18:00 出发
  - 性价比优先：按价格从低到高排序
- **去重逻辑**：同一航线同一日期只保留最便宜的一个
- **结果输出**：生成 Excel 文件，包含 Top10 高性价比方案

## 快速开始

### 环境要求

```bash
Python 3.8+
```

### 安装依赖

```bash
pip install pandas selenium selenium-wire openpyxl python-magic-bin
```

### 浏览器驱动

需要下载对应浏览器版本的 WebDriver：
- Edge: [Microsoft Edge WebDriver](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/)
- Chrome: [ChromeDriver](https://sites.google.com/chromium.org/driver/)

## 使用说明

### 1. 配置爬虫

编辑 `ctrip_flights_scraper_V1.py` 中的配置区域：

```python
# 出发城市
ORIGIN_CITIES = ["重庆", "昆明", "丽江", "大理", "厦门", "福州"]
# 目的地
DEST_CITIES = ["NRT", "HND", "KIX", "ICN", "GMP", "HKG", "TPE"]
# 日期配置
begin_date = '2026-04-05'
end_date = '2026-04-06'
```

### 2. 运行爬虫

```bash
python ctrip_flights_scraper_V1.py
```

爬虫会自动：
- 打开浏览器
- 处理登录/验证码（如需人工操作会在控制台提示）
- 筛选上海中转航班
- 按低价排序
- 保存数据到 `./日期/数据获取日期/出发-到达.csv`

### 3. 运行分析

```bash
python analyze.py
```

分析脚本会自动：
- 读取所有 CSV 文件
- 整合数据
- 筛选 15:00-18:00 出发的上海中转航班
- 按价格排序
- 生成 `top10_flights_YYYYMMDD_HHMMSS.xlsx`

## 文件结构

```
.
├── ctrip_flights_scraper_V1.py  # 爬虫主程序
├── analyze.py                       # 数据分析主程序
├── cookies.json                     # 登录 Cookie 缓存（自动生成）
├── screenshot/                      # 调试截图目录（自动生成）
├── 2026-04-04/                     # 按航班日期组织的数据目录
│   └── 2026-03-25/
│       ├── 重庆-东京.csv
│       └── 重庆-大阪.csv
└── top10_flights_20260325_163000.xlsx  # 分析结果
```

## 配置说明

### 爬虫配置 (`ctrip_flights_scraper_V4.1.py`)

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `ORIGIN_CITIES` | 出发城市列表 | `["重庆", "昆明", "厦门"]` |
| `DEST_CITIES` | 目的地列表（支持IATA代码） | `["NRT", "HKG", "TPE"]` |
| `begin_date` | 开始日期 | `'2026-04-04'` |
| `end_date` | 结束日期 | `'2026-04-10'` |
| `crawl_interval` | 爬取间隔（秒） | `5` |
| `max_wait_time` | 页面等待超时（秒） | `20` |
| `accounts` / `passwords` | 携程账号密码 | `['your_account']` |
| `enable_screenshot` | 是否开启截图调试 | `True` |

### 分析配置 (`analyze.py`)

分析脚本无需配置，直接运行即可。默认筛选逻辑：
- 中转城市：上海
- 出发时间：15:00-18:00
- 排序：价格从低到高
- 输出：Top10

如需修改筛选条件，可编辑 `filter_top10_flights` 函数中的时间判断逻辑。

---

## 📝 注意事项

1. **数据用途**：仅供个人学习和研究使用，请勿用于商业用途
2. **页面变化**：携程页面结构可能变化，如遇爬取失败需更新选择器

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

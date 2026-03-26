import os
import pandas as pd
import re
from datetime import datetime, timedelta
from pathlib import Path

# ==================== 1. 数据读取与整合 ====================
def load_all_flight_data(root_dir: str = ".") -> pd.DataFrame:
    """
    读取所有爬取的CSV文件并整合到一张表
    保存路径逻辑：./日期/数据获取日期/出发-到达.csv
    """
    all_data = []
    
    # 遍历所有日期目录
    for date_dir in Path(root_dir).iterdir():
        if not date_dir.is_dir():
            continue
        # 检查是否是日期格式目录（YYYY-MM-DD）
        if not re.match(r'\d{4}-\d{2}-\d{2}', date_dir.name):
            continue
            
        # 遍历日期目录下的数据获取日期目录
        for fetch_date_dir in date_dir.iterdir():
            if not fetch_date_dir.is_dir():
                continue
                
            # 遍历所有CSV文件
            for csv_file in fetch_date_dir.glob("*.csv"):
                try:
                    # 尝试多种编码读取
                    try:
                        df = pd.read_csv(csv_file, encoding="UTF-8-sig")
                    except:
                        try:
                            df = pd.read_csv(csv_file, encoding="gbk")
                        except:
                            df = pd.read_csv(csv_file, encoding="utf-8")
                    
                    # 跳过空文件（只有表头）
                    if len(df) == 0:
                        continue
                        
                    # 添加文件来源信息，方便追溯
                    df['_source_file'] = str(csv_file)
                    df['_flight_date'] = date_dir.name  # 航班日期
                    all_data.append(df)
                    print(f"已读取: {csv_file} ({len(df)} 条)")
                except Exception as e:
                    print(f"读取失败 {csv_file}: {e}")
    
    if not all_data:
        print("未找到任何数据文件")
        return pd.DataFrame()
    
    # 合并所有数据
    merged_df = pd.concat(all_data, ignore_index=True)
    print(f"\n整合完成，共 {len(merged_df)} 条数据")
    return merged_df

# ==================== 2. 修复后的智能筛选函数 ====================
def filter_top10_flights(df: pd.DataFrame) -> pd.DataFrame:
    """
    完整版智能筛选与排序：
    优先级：
    1. 直飞航班（首选）
    2. 上海中转航班
    3. 15:00-18:00出发的优先
    4. 价格从低到高
    """
    if df.empty:
        print("输入数据为空")
        return df
    
    print(f"\n原始数据条数: {len(df)}")
    
    # ==================== 1. 数据清洗与预处理 ====================
    df_processed = df.copy()
    
    # 打印中转城市值分布
    if '中转城市' in df_processed.columns:
        print(f"\n中转城市值分布:")
        print(df_processed['中转城市'].value_counts(dropna=False))
    
    # ==================== 2. 智能标记航班类型 ====================
    def mark_flight_type(row):
        """标记航班类型：直飞、上海中转、其他"""
        transit_city = str(row.get('中转城市', '')).strip()
        
        # 判断是否是直飞（中转城市为空、或包含"直飞"、或到达城市是上海）
        arrival_city = str(row.get('到达城市', '')).strip()
        if (pd.isna(row.get('中转城市')) or 
            transit_city == '' or 
            '直飞' in transit_city or
            arrival_city == '上海'):
            return '直飞'
        
        # 判断是否是上海中转
        if '上海' in transit_city:
            return '上海中转'
        
        # 其他中转
        return '其他中转'
    
    df_processed['_flight_type'] = df_processed.apply(mark_flight_type, axis=1)
    
    print(f"\n航班类型分布:")
    print(df_processed['_flight_type'].value_counts())
    
    # ==================== 3. 时间解析与标记 ====================
    def parse_time_simple(time_str):
        """简化版时间解析，只提取HH:MM"""
        if pd.isna(time_str):
            return None
        time_str = str(time_str).strip()
        match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            return f"{match.group(1).zfill(2)}:{match.group(2)}"
        return None
    
    # 解析出发时间
    df_processed['_depart_time_str'] = df_processed['出发时间'].apply(parse_time_simple)
    
    # 标记是否在15:00-18:00之间
    def is_in_time_range(time_str):
        if not time_str:
            return False
        try:
            hour = int(time_str.split(':')[0])
            return 15 <= hour < 18
        except:
            return False
    
    df_processed['_is_target_time'] = df_processed['_depart_time_str'].apply(is_in_time_range)
    
    print(f"\n目标时间段（15:00-18:00）航班数: {df_processed['_is_target_time'].sum()}")
    
    # ==================== 4. 价格清洗 ====================
    def clean_price_simple(price_val):
        if pd.isna(price_val):
            return 999999
        if isinstance(price_val, (int, float)):
            return int(price_val)
        price_str = str(price_val)
        digits = re.findall(r'\d', price_str)
        if digits:
            return int(''.join(digits))
        return 999999
    
    df_processed['_price_num'] = df_processed['价格'].apply(clean_price_simple)
    
    # ==================== 5. 智能排序（核心逻辑） ====================
    # 构造排序优先级：
    # 1. 航班类型优先级：直飞(0) > 上海中转(1) > 其他中转(2)
    type_priority = {'直飞': 0, '上海中转': 1, '其他中转': 2}
    df_processed['_type_priority'] = df_processed['_flight_type'].map(type_priority).fillna(2)
    
    # 2. 时间段优先级：目标时间段(0) > 其他(1)
    df_processed['_time_priority'] = df_processed['_is_target_time'].apply(lambda x: 0 if x else 1)
    
    # 3. 价格优先级：直接用价格
    df_processed['_price_priority'] = df_processed['_price_num']
    
    # 最终排序：类型优先级 -> 时间段优先级 -> 价格
    df_sorted = df_processed.sort_values(
        by=['_type_priority', '_time_priority', '_price_priority'],
        ascending=[True, True, True]
    )
    
    print(f"\n智能排序完成")
    print(f"Top5航班类型: {df_sorted['_flight_type'].head(5).tolist()}")
    print(f"Top5价格: {df_sorted['_price_num'].head(5).tolist()}")
    
    # ==================== 6. 严格去重 ====================
    # 唯一key：出发城市-到达城市-航班日期-出发时间
    df_sorted['_unique_key'] = (
        df_sorted['出发城市'].astype(str) + '-' +
        df_sorted['到达城市'].astype(str) + '-' +
        df_sorted['_flight_date'].astype(str) + '-' +
        df_sorted['出发时间'].astype(str)
    )
    
    df_dedup = df_sorted.drop_duplicates(subset=['_unique_key'], keep='first')
    
    print(f"\n去重前: {len(df_sorted)} 条，去重后: {len(df_dedup)} 条")
    
    # 取Top10
    df_top10 = df_dedup.head(10).copy()
    
    # ==================== 7. 输出友好的列 ====================
    output_columns = [
        '_flight_date', '出发城市', '出发机场', '出发时间', 
        '到达城市', '到达机场', '到达时间', '次日到达',
        '中转城市', '_flight_type', '航空公司', '航班号', '机型', 
        '飞行时长', '价格'
    ]
    output_columns = [col for col in output_columns if col in df_top10.columns]
    
    if '_flight_date' in output_columns:
        df_top10 = df_top10.rename(columns={'_flight_date': '航班日期'})
        output_columns[output_columns.index('_flight_date')] = '航班日期'
    
    if '_flight_type' in output_columns:
        df_top10 = df_top10.rename(columns={'_flight_type': '航班类型'})
        output_columns[output_columns.index('_flight_type')] = '航班类型'
    
    print(f"\n最终Top10筛选完成")
    return df_top10[output_columns]

# ==================== 主程序 ====================
if __name__ == "__main__":
    # 1. 整合所有数据
    print("="*60)
    print("开始整合数据...")
    print("="*60)
    all_flights = load_all_flight_data(".")
    
    if all_flights.empty:
        print("没有数据可处理")
    else:
        # 2. 筛选Top20
        print("\n" + "="*60)
        print("开始智能筛选 Top10 方案...")
        print("="*60)
        top20_flights = filter_top10_flights(all_flights)
        
        if not top20_flights.empty:
            # 3. 保存结果
            output_file = f"top20_flights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            top20_flights.to_excel(output_file, index=False, engine='openpyxl')
            
            print("\n" + "="*60)
            print(f"Top10 方案已保存到: {output_file}")
            print("="*60)
            
            # 4. 打印预览
            print("\nTop10 方案预览：")
            print(top20_flights.to_string(index=False))
        else:
            print("未能生成Top10方案")

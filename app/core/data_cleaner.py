"""
数据清洗引擎
处理Excel导入，自动识别报表类型，字段清洗，数据校验
"""
import os
import re
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
import pandas as pd

from app.constants import ReportType, IMPORT_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DataCleaner:
    """数据清洗类"""
    
    def __init__(self):
        self.report_type_map = {
            ReportType.DAILY_ROOM: ["日租房", "过夜房", "日租"],
            ReportType.HOURLY_ROOM: ["钟点房", "小时房", "时租"],
            ReportType.OTHER_CONSUME: ["其他消费", "额外消费", "其他"],
            ReportType.INCOME_CHECK: ["应收收入", "营业收入", "对账"]
        }
        # OTA最低价不再过滤，所有正价房间均计入起售价
        self.min_valid_price = 0.0
    
    def identify_report_type(self, df: pd.DataFrame, sheet_name: str) -> str:
        """
        识别报表类型
        :param df: DataFrame数据
        :param sheet_name: Sheet名称
        :return: 报表类型
        """
        # 先通过Sheet名称匹配
        for report_type, keywords in self.report_type_map.items():
            for kw in keywords:
                if kw in sheet_name:
                    return report_type

        # 再通过表头关键字匹配（去呼呼实际导出列名）
        columns = "".join([str(col) for col in df.columns])
        # 也检查第一行数据中的文本
        first_row_text = ""
        if not df.empty:
            first_row_text = "".join([str(v) for v in df.iloc[0].values if pd.notna(v)])
        all_text = columns + first_row_text

        # 日租房概况特征：间夜数/过夜/日租 + 房费
        if ("间夜数" in all_text or "过夜" in all_text or "日租" in all_text or "间夜" in all_text) and "房费" in all_text:
            return ReportType.DAILY_ROOM

        # 钟点房概况特征：小时/钟点 + 房费
        if ("小时" in all_text or "钟点" in all_text or "时租" in all_text) and "房费" in all_text:
            return ReportType.HOURLY_ROOM

        # 其他消费概况特征：消费项目/其他消费/商品 + 金额
        if ("消费项目" in all_text or "其他消费" in all_text or "商品" in all_text or "消费" in all_text) and "金额" in all_text:
            return ReportType.OTHER_CONSUME

        # 营业收入特征：营业收入/应收收入/应收
        if "营业收入" in all_text or "应收收入" in all_text or "应收" in all_text:
            return ReportType.INCOME_CHECK

        raise ValueError(f"无法识别报表类型，Sheet名称：{sheet_name}, 列名：{list(df.columns)[:5]}")
    
    def clean_number(self, value: Any) -> float:
        """
        清洗数值字段，去除货币符号、千分位逗号
        :param value: 原始值
        :return: 清洗后的数值
        """
        # 检查值是否为NaN（缺失值）
        if pd.isna(value):
            return 0.0
        # 如果值已经是整数或浮点数，直接转换为float返回
        if isinstance(value, (int, float)):
            return float(value)
        # 去除非数字字符（保留小数点和负号）
        value_str = str(value).strip()
        value_str = re.sub(r"[^\d.-]", "", value_str)
        try:
            return float(value_str) if value_str else 0.0
        except ValueError:
            return 0.0
    
    def clean_int(self, value: Any) -> int:
        """清洗整数字段"""
        return int(self.clean_number(value))
    
    def extract_date(self, file_name: str, df: pd.DataFrame) -> str:
        """
        提取报表日期
        优先从文件名提取，其次从表头提取
        :param file_name: 文件名
        :param df: DataFrame
        :return: 日期字符串YYYY-MM-DD
        """
        # 从文件名匹配日期
        date_pattern = r"(\d{4}-\d{1,2}-\d{1,2})|(\d{4}/\d{1,2}/\d{1,2})|(\d{8})"
        match = re.search(date_pattern, file_name)
        if match:
            date_str = match.group()
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                try:
                    return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
        
        # 从表头查找日期
        for col in df.columns:
            col_str = str(col)
            if "日期" in col_str:
                first_val = df[col].iloc[0]
                if isinstance(first_val, datetime):
                    return first_val.strftime("%Y-%m-%d")
                if isinstance(first_val, str):
                    for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
                        try:
                            return datetime.strptime(first_val, fmt).strftime("%Y-%m-%d")
                        except ValueError:
                            continue
        
        # 默认返回今天
        return datetime.now().strftime("%Y-%m-%d")
    
    def parse_excel(self, file_path: str) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        解析去呼呼导出的Excel文件
        :return: (报表日期, 清洗后的数据{room_count, total_fee, min_price}, 错误列表)
        """
        errors = []
        result = {"room_count": 0, "total_fee": 0.0, "min_price": 0.0}

        try:
            file_name = os.path.basename(file_path)
            xls = pd.ExcelFile(file_path)
            report_date = ""
            all_rooms = 0
            all_fee = 0.0
            all_min = float("inf")

            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                if df.empty:
                    continue

                # 去呼呼导出格式：第一行是大标题（含日期），第二行是子表头
                # 例：Row0="房间销售明细(支付类型为:全部,订单状态为:全部的订单,2026-07-19到2026-07-19)营业收入"
                #     Row1=房型/房间 | NaN | 2026-07-19 | 合计
                #     数据从Row2开始，最后一行为"总计"

                # 从标题行提取日期
                if len(df) > 0:
                    header_text = str(df.iloc[0, 0]) if pd.notna(df.iloc[0, 0]) else ""
                    date_match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", header_text)
                    if date_match:
                        report_date = date_match.group(1)

                # 找到数据起始行（跳过标题和子表头）
                data_start = 0
                for i in range(len(df)):
                    row_text = " ".join([str(v) for v in df.iloc[i].values if pd.notna(v)])
                    # 子表头特征：包含"房型"或"房间"
                    if "房型" in row_text or "房间" in row_text:
                        data_start = i + 1
                        break

                if data_start == 0:
                    data_start = 2  # 默认跳过前2行

                # 提取数据：第2列=房间号(index 1)，第3列=费用(index 2)
                room_col_idx = 1   # Unnamed:1 → 房间号
                fee_col_idx = 2    # Unnamed:2 → 日房费

                room_count = 0
                total_fee = 0.0
                min_price = float("inf")

                for i in range(data_start, len(df)):
                    row = df.iloc[i]
                    room_val = row.iloc[room_col_idx] if room_col_idx < len(row) else None
                    fee_val = row.iloc[fee_col_idx] if fee_col_idx < len(row) else None

                    # 检测汇总行
                    room_str = str(room_val).strip() if pd.notna(room_val) else ""
                    if "总计" in room_str or "合计" in room_str:
                        total_fee = self.clean_number(fee_val)
                        break

                    # 检查是否是有效数据行（房间号是数字）
                    try:
                        room_num = int(float(str(room_val)))
                    except (ValueError, TypeError):
                        continue

                    fee = self.clean_number(fee_val)
                    if fee > 0:
                        room_count += 1
                        total_fee += fee
                        # ★ 排除钟点房：低于最低有效OTA价的房间不计入起售价
                        if fee >= self.min_valid_price and fee < min_price:
                            min_price = fee

                all_rooms += room_count
                all_fee += total_fee
                if min_price < all_min:
                    all_min = min_price

                logger.info(f"  Sheet[{sheet_name}]: 房间={room_count}, 房费={total_fee}, 最低={min_price}")

            if not report_date:
                report_date = self.extract_date(file_name, pd.DataFrame())

            result["room_count"] = all_rooms
            result["total_fee"] = round(all_fee, 2)
            result["min_price"] = all_min if all_min != float("inf") else 0.0

            if all_rooms < 0 or all_rooms > 200:
                errors.append(f"房间数{all_rooms}超出合理范围(0-200)")
            if all_fee < 0:
                errors.append(f"房费{all_fee}不能为负数")

            return report_date, result, errors

        except Exception as e:
            logger.error(f"解析Excel失败：{str(e)}", exc_info=True)
            errors.append(f"文件解析失败：{str(e)}")
            return "", result, errors

    def parse_source_excel(self, file_path: str) -> Dict[str, Any]:
        """
        解析订单来源明细Excel（客源统计导出）
        格式: 渠道名称 | 预定类型 | 订单数 | 订单数占比 | 间夜数 | 间夜数占比 | 总房费 | 总房费占比
        :return: {channels: [{channel, pay_type, orders, room_nights, revenue}], ...}
        """
        result = {"channels": []}
        try:
            df = pd.read_excel(file_path, header=None)
            if df.empty or len(df) < 2:
                return result

            for i in range(1, len(df)):
                row = df.iloc[i]
                channel = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                pay_type = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                if not channel or channel == "nan":
                    continue

                orders = int(float(str(row.iloc[2]))) if pd.notna(row.iloc[2]) else 0
                room_nights = float(str(row.iloc[4])) if pd.notna(row.iloc[4]) else 0  # 间夜数（非占比）
                revenue = float(str(row.iloc[6])) if pd.notna(row.iloc[6]) else 0.0

                result["channels"].append({
                    "channel": channel,
                    "pay_type": pay_type,
                    "orders": orders,
                    "room_nights": room_nights,
                    "revenue": revenue,
                })
        except Exception as e:
            logger.error(f"解析订单来源明细失败: {e}")
        return result

    def parse_monthly_excel(self, file_path: str) -> List[Dict[str, Any]]:
        """
        解析月度客房销售明细Excel（多日列式）
        结构: 行1=日期头(每列一天)，行2-N=房间数据，末行=总计
        :return: [{date, room_count, total_fee, min_price}, ...]
        """
        results = []
        try:
            df = pd.read_excel(file_path, header=None)
            if df.empty or df.shape[0] < 3 or df.shape[1] < 4:
                return results

            # Row 1: 子表头 房型/房间 | NaN | 2026-07-01 | 2026-07-02 | ... | 合计
            header_row = df.iloc[1]
            date_cols = {}  # {col_index: date_string}
            for j in range(2, df.shape[1]):
                val = str(header_row.iloc[j]) if pd.notna(header_row.iloc[j]) else ""
                if val == "合计":
                    break
                if re.match(r"\d{4}-\d{2}-\d{2}", val):
                    date_cols[j] = val

            if not date_cols:
                return results

            # 数据行：从第2行到倒数第2行（最后一行是总计）
            data_end = len(df) - 1
            last_row_text = " ".join([str(v) for v in df.iloc[-1].values if pd.notna(v)])
            if "总计" not in last_row_text:
                data_end = len(df)  # 没有总计行

            # 对每个日期列统计
            for col_idx, date_str in date_cols.items():
                room_count = 0
                total_fee = 0.0
                min_price = float("inf")

                for i in range(2, data_end):
                    fee_val = df.iloc[i, col_idx] if col_idx < df.shape[1] else None
                    fee = self.clean_number(fee_val)
                    if fee > 0:
                        room_count += 1
                        total_fee += fee
                        if fee < min_price:
                            min_price = fee

                if min_price == float("inf"):
                    min_price = 0.0

                results.append({
                    "date": date_str,
                    "room_count": room_count,
                    "total_fee": round(total_fee, 2),
                    "min_price": round(min_price, 2),
                })

        except Exception as e:
            logger.error(f"解析月度Excel失败: {e}")

        return results

    def _find_column(self, df: pd.DataFrame, keywords: List[str]) -> Optional[Any]:
        """根据关键词查找DataFrame中的列名"""
        for col in df.columns:
            col_str = str(col)
            for kw in keywords:
                if kw in col_str:
                    return col
        return None

    def _smart_sum(self, df: pd.DataFrame, col) -> float:
        """
        智能求和：如果最后一行看起来是汇总行（前面有"合计"/"总计"等字样），
        则取最后一行的值；否则对所有行求和。
        自动将列转换为数值类型，处理货币符号等。
        """
        if not col or col not in df.columns:
            return 0.0
        if len(df) == 0:
            return 0.0

        # ★ 先将列转为数值（处理 ¥、千分位等）
        numeric_col = df[col].apply(self.clean_number)

        # 检查最后一行是否包含汇总关键词
        last_row = df.iloc[-1]
        row_text = "".join([str(v) for v in last_row.values if pd.notna(v)])
        if any(kw in row_text for kw in ["合计", "总计", "汇总", "小计"]):
            return self.clean_number(last_row[col])

        # 对清洗后的数值列求和
        return float(numeric_col.sum())

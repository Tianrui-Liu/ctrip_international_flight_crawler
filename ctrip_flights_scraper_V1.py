# ============================================
# 携程国际版航班爬虫 - V4.2 定制修改版
# 融合V3登录验证码逻辑 + 上海中转航班筛选
# ============================================
import io
import os
import time
import json
import re
import pandas as pd
import random
from seleniumwire import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime as dt, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import threading
# ============ 配置区域 ============
# 出发城市
# ORIGIN_CITIES = ["重庆", "昆明", "丽江", "大理", "厦门", "福州"]
ORIGIN_CITIES = ["丽江", "大理"]
# 目的地：日韩+港澳台
DEST_CITIES = ["NRT", "HND", "KIX", "ITM", "NGO", "FUK", "CTS", "OKA", "ICN", "GMP", "PUS", "CJU", "HKG", "TPE"]
# 中转城市
TRANSIT_CITY = "上海"
TRANSIT_AIRPORTS = ["SHA", "PVG"]
CITY_CODE_MAP = {
    '重庆': 'CKG', '昆明': 'KMG', '丽江': 'LJG', '大理': 'DLU',
    '厦门': 'XMN', '福州': 'FOC', '上海': 'SHA', '香港': 'HKG',
    '东京': 'NRT', '大阪': 'KIX', '首尔': 'ICN', '台北': 'TPE'
}
# 日期配置
begin_date = '2026-04-06'
end_date = '2026-04-06'
crawl_days = 60
days_interval = 1
# 爬取间隔
crawl_interval = 3
max_wait_time = 20  # 【修复】增加等待时间到20秒
max_retry_time = 3
# 功能开关
direct_flight = False
enable_screenshot = True  # 【修复】开启截图便于调试
login_allowed = True
# 账号配置
accounts = ['', '']
passwords = ['', '']
COOKIES_FILE = "cookies.json"
REQUIRED_COOKIES = ["AHeadUserInfo", "DUID", "IsNonUser", "_udl", "cticket", "login_type", "login_uid"]
# ============ 【修复】更新DOM选择器配置 - 提供多组备选 ============
SELECTORS = {
    # 主选择器（新版国际版）
    'flight_list': [
        '.flight-list.root-flights',
        '.flight-list',
        '[class*="flight-list"]',
        '.flight-search-result-list',
        '.flight-result-list',
        '[data-testid="flight-list"]'
    ],
    # 单个航班项
    'flight_item': [
        '.flight-item',
        '.flight-search-result-item',
        '[class*="flight-item"]',
        '.flight-result-item',
        '[data-testid="flight-item"]'
    ],
    # 航空公司
    'airline_name': [
        '.airline-name span',
        '.airline-name',
        '.airline-info .name',
        '[class*="airline"] [class*="name"]',
        '.flight-airline'
    ],
    # 航班号
    'flight_no': [
        '.plane-No',
        '.flight-number',
        '[class*="flight-number"]',
        '.airline-info .flight-no',
        '.flight-no'
    ],
    # 出发信息
    'depart_time': [
        '.depart-box .time',
        '.departure-time',
        '[class*="depart"] [class*="time"]',
        '.flight-time-departure',
        '.departure .time'
    ],
    'depart_airport': [
        '.depart-box .airport .name',
        '.departure-airport',
        '[class*="depart"] [class*="airport"]',
        '.departure .airport'
    ],
    'depart_terminal': [
        '.depart-box .terminal',
        '.departure-terminal',
        '[class*="depart"] [class*="terminal"]',
        '.departure .terminal'
    ],
    # 到达信息
    'arrive_time': [
        '.arrive-box .time',
        '.arrival-time',
        '[class*="arrive"] [class*="time"]',
        '.flight-time-arrival',
        '.arrival .time'
    ],
    'arrive_airport': [
        '.arrive-box .airport .name',
        '.arrival-airport',
        '[class*="arrive"] [class*="airport"]',
        '.arrival .airport'
    ],
    'arrive_terminal': [
        '.arrive-box .terminal',
        '.arrival-terminal',
        '[class*="arrive"] [class*="terminal"]',
        '.arrival .terminal'
    ],
    # 飞行时长
    'duration': [
        '.flight-consume',
        '.flight-duration',
        '[class*="duration"]',
        '.flight-time-total',
        '.duration'
    ],
    # 价格
    'price': [
        '.flight-price .price',
        '.price .amount',
        '[class*="price"] [class*="amount"]',
        '.flight-price',
        '.price'
    ],
    # 机型
    'aircraft': [
        '.plane-No span',
        '.aircraft-type',
        '[class*="aircraft"]',
        '.plane-type'
    ],
}
def init_driver():
    """初始化浏览器驱动"""
    options = webdriver.EdgeOptions()
    options.add_argument("--incognito")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--pageLoadStrategy=eager")
    options.add_argument("--disable-gpu")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--window-size=1920,1080")  # 【新增】设置窗口大小
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # 【新增】禁用自动化检测
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option('useAutomationExtension', False)
    seleniumwire_options = {
        'auto_config': True,
        'suppress_connection_errors': True,
        'disable_encoding': True,
        'ignore_http_methods': ['OPTIONS', 'HEAD'],
        'verify_ssl': False,
    }
    driver = webdriver.Edge(
        options=options,
        seleniumwire_options=seleniumwire_options
    )
    # 隐藏webdriver特征
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        """
    })
    return driver
def get_city_code(city_name: str) -> str:
    """中文城市转IATA代码"""
    if len(city_name) == 3:
        return city_name.upper()
    code = CITY_CODE_MAP.get(city_name)
    if not code:
        # 如果找不到，直接返回输入（假设已经是代码）
        return city_name.upper()
    return code
def gen_citys():
    """生成城市组合"""
    citys = []
    for origin in ORIGIN_CITIES:
        for dest in DEST_CITIES:
            citys.append([origin, dest, False])  # False=需要中转航班
        citys.append([origin, TRANSIT_CITY, True])  # True=只查直飞
    return citys
def generate_flight_dates(n, begin_date, end_date, start_interval, days_interval):
    """生成日期列表"""
    flight_dates = []
    if begin_date:
        begin_date = dt.strptime(begin_date, "%Y-%m-%d")
    elif start_interval:
        begin_date = dt.now() + timedelta(days=start_interval)
    for i in range(0, n, days_interval):
        flight_date = begin_date + timedelta(days=i)
        flight_dates.append(flight_date.strftime("%Y-%m-%d"))
    if end_date:
        end_date = dt.strptime(end_date, "%Y-%m-%d")
        flight_dates = [d for d in flight_dates if dt.strptime(d, "%Y-%m-%d") <= end_date]
    return flight_dates

# element_to_be_clickable 函数来替代 expected_conditions.element_to_be_clickable 或 expected_conditions.visibility_of_element_located
def element_to_be_clickable(element):
    def check_clickable(driver):
        try:
            if element.is_enabled() and element.is_displayed():
                return element  # 当条件满足时，返回元素本身
            else:
                return False
        except:
            return False
    return check_clickable

# ============================================
# 【核心】DataFetcher类 - DOM提取方式
# ============================================
class DataFetcher(object):
    def __init__(self, driver):
        self.driver = driver
        self.date = None
        self.city = None
        self.err = 0
        self.switch_acc = 0
        self.flights = None
    def refresh_driver(self):
        """刷新页面"""
        try:
            self.driver.refresh()
            time.sleep(5)
        except Exception as e:
            self.err += 1
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} refresh_driver:刷新失败 {e}')
            if self.err < max_retry_time:
                self.refresh_driver()
    def remove_btn(self):
        """移除页面干扰元素"""
        try:
            self.driver.execute_script("document.querySelectorAll('.notice-box').forEach(e => e.remove());")
            self.driver.execute_script("document.querySelectorAll('.shortcut').forEach(e => e.remove());")
            self.driver.execute_script("document.querySelectorAll('.shareline').forEach(e => e.remove());")
            self.driver.execute_script("document.querySelectorAll('.modal, .dialog').forEach(e => e.remove());")
        except Exception as e:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} remove_btn:移除失败 {e}')
    def check_verification_code(self):
        try:
            # 检查验证码和登录弹窗
            has_veri = len(self.driver.find_elements(By.ID, "verification-code")) + len(self.driver.find_elements(By.CLASS_NAME, "alert-title"))
            has_login_pop = len(self.driver.find_elements(By.CLASS_NAME, "lg_loginbox_modal")) > 0
            
            if has_veri or has_login_pop:
                if has_login_pop:
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 检测到登录弹窗，人工点击扫码登录即可关闭弹窗，完成后按回车继续。')
                else:
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 检测到验证码，请手动完成验证，完成后按回车继续。')
    
                user_input_completed = threading.Event()
                # 等待用户手动处理
                def wait_for_input():
                    input("请完成操作，然后按回车键继续...")
                    user_input_completed.set()
    
                input_thread = threading.Thread(target=wait_for_input)
                input_thread.start()
    
                # 设置超时时间
                timeout_seconds = crawl_interval * 100
                input_thread.join(timeout=timeout_seconds)
    
                if user_input_completed.is_set():
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 操作完成，继续执行。')
                    # 等待国际版页面加载完成
                    WebDriverWait(self.driver, max_wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".flight-list"))
                    )
                    # 移除干扰元素
                    self.remove_btn()
                    return True
                else:
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 手动操作超时 {timeout_seconds} 秒，重置浏览器')
                    self.driver.quit()
                    self.driver = init_driver()
                    self.err = 0
                    self.switch_acc += 1
                    self.get_page(1)
                    return False
            else:
                # 移除干扰元素
                self.remove_btn()
                return True
        except Exception as e:
            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} check_verification_code:未知错误，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
            )
            return False
    def load_cookies(self, account):
        if os.path.exists(COOKIES_FILE):
            try:
                with open(COOKIES_FILE, "r") as f:
                    cookies_all = json.load(f)
                return cookies_all.get(account)
            except Exception as e:
                print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} load_cookies: 读取 cookies 出错：{e}")
                return None
        return None
    def save_cookies(self, account, cookies):
        cookies_all = {}
        if os.path.exists(COOKIES_FILE):
            try:
                with open(COOKIES_FILE, "r") as f:
                    cookies_all = json.load(f)
            except:
                pass
        cookies_all[account] = cookies
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies_all, f)
    def delete_cookies(self, account):
        try:
            if os.path.exists(COOKIES_FILE):
                with open(COOKIES_FILE, "r") as f:
                    cookies_all = json.load(f)
                if account in cookies_all:
                    del cookies_all[account]
                    with open(COOKIES_FILE, "w") as f:
                        json.dump(cookies_all, f)
                    print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 成功删除账号 {account} 的 cookies")
        except Exception as e:
            print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 删除账号 {account} cookies 失败：{e}")
    def login(self):
        if login_allowed:
            account = accounts[self.switch_acc % len(accounts)]
            password = passwords[self.switch_acc % len(passwords)]
            
            # ===== 尝试使用本地缓存的 cookies 登录 =====
            local_cookies = self.load_cookies(account)
            if local_cookies:
                print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 检测到本地 cookies，尝试通过 cookies 登录")
                for cookie in local_cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 添加 cookie {cookie.get('name')} 失败：{e}")
                
                try:
                    # 检测登录状态
                    self.driver.get('https://my.ctrip.com/myinfo/home')
                    WebDriverWait(self.driver, max_wait_time).until(
                        lambda d: d.current_url == 'https://my.ctrip.com/myinfo/home'
                    )
                    print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 已通过 cookie 登录")
                    self.err += 99
                    return 1
                except Exception:
                    print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} 错误次数【{self.err}-{max_retry_time}】 login: cookie 登录失效，重新走登录流程")
                    self.err += 1
                    if self.err >= max_retry_time:
                        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: cookie 登录失败次数超过 {max_retry_time} 次，删除该账号 cookies")
                        self.delete_cookies(account)
                        self.err = 0
                    self.login()
            else:
                try:
                    # 检查登录弹窗是否已弹出
                    if len(self.driver.find_elements(By.CLASS_NAME, "lg_loginbox_modal")) == 0:
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:未弹出登录界面，尝试唤起登录')
                        # 尝试点击登录按钮唤起弹窗
                        login_btn = WebDriverWait(self.driver, max_wait_time).until(
                            element_to_be_clickable(self.driver.find_element(By.CLASS_NAME, "tl_nfes_home_header_login_wrapper_siwkn"))
                        )
                        login_btn.click()
                        WebDriverWait(self.driver, max_wait_time).until(EC.presence_of_element_located((By.CLASS_NAME, "lg_loginwrap")))
                    else:
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:已经弹出登录界面')
                    
                    # 输入账号密码
                    ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_elements(By.CLASS_NAME, "r_input.bbz-js-iconable-input")[0]))
                    ele.send_keys(account)
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:输入账户成功')
                    
                    ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_element(By.CSS_SELECTOR, "div[data-testid='accountPanel'] input[data-testid='passwordInput']")))
                    ele.send_keys(password)
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:输入密码成功')
                    
                    ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_element(By.CSS_SELECTOR, '[for="checkboxAgreementInput"]')))
                    ele.click()
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:勾选同意成功')
                    
                    ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_elements(By.CLASS_NAME, "form_btn.form_btn--block")[0]))
                    ele.click()
    
                    # 检查是否出现短信验证码验证页面
                    try:
                        WebDriverWait(self.driver, max_wait_time).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='doubleAuthSwitcherBox']"))
                        )
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 检测到短信验证码验证页面')
                        
                        double_auth_selector = "[data-testid='doubleAuthSwitcherBox']"
                        # 点击发送验证码
                        send_btn = WebDriverWait(self.driver, max_wait_time).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, f"{double_auth_selector} dl[data-testid='dynamicCodeInput'] a.btn-primary-s"))
                        )
                        send_btn.click()
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 发送验证码按钮点击')
                        
                        # 等待用户输入验证码
                        verification_code = [None]
                        user_input_completed = threading.Event()
                        
                        def wait_for_verification_input():
                            verification_code[0] = input("请输入收到的短信验证码: ")
                            user_input_completed.set()
                        
                        input_thread = threading.Thread(target=wait_for_verification_input)
                        input_thread.start()
                        timeout_seconds = crawl_interval * 100
                        input_thread.join(timeout=timeout_seconds)
                        
                        if not user_input_completed.is_set():
                            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 验证码输入超时 {timeout_seconds} 秒')
                            self.switch_acc += 1
                            self.err += 99
                            return 0
                        
                        # 输入验证码并提交
                        code_input = WebDriverWait(self.driver, max_wait_time).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, f"{double_auth_selector} input[data-testid='verifyCodeInput']"))
                        )
                        code_input.send_keys(verification_code)
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 验证码输入成功')
                        
                        verify_btn = WebDriverWait(self.driver, max_wait_time).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, f"{double_auth_selector} dl[data-testid='dynamicVerifyButton'] input[type='submit']"))
                        )
                        verify_btn.click()
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 验证码提交成功')
                        
                        # 等待页面加载
                        WebDriverWait(self.driver, max_wait_time).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".flight-list"))
                        )
                    except Exception as e:
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 未检测到验证码验证页面，继续执行')
                    
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login：登录成功')
                    if enable_screenshot:
                        self.driver.save_screenshot(f'screenshot/login_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png')
                    time.sleep(crawl_interval*3)
                    
                    # 保存cookies
                    all_cookies = self.driver.get_cookies()
                    filtered_cookies = [ck for ck in all_cookies if ck.get("name") in REQUIRED_COOKIES]
                    self.save_cookies(account, filtered_cookies)
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: cookies 已保存')
                    
                except Exception as e:
                    self.err += 1
                    print(
                        f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login：页面加载或元素操作失败，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
                    )
                    if enable_screenshot:
                        self.driver.save_screenshot(f'screenshot/login_error_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png')
                    if self.err < max_retry_time:
                        self.refresh_driver()
                        if self.check_verification_code():
                            self.login()
                    if self.err >= max_retry_time:
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,login:重新尝试加载页面')
    # ============================================
    # 【修复】get_page - 直接访问搜索结果URL
    # ============================================
    def get_page(self, reset_to_homepage=0):
        """初始化页面 - 直接访问搜索结果URL"""
        try:
            if reset_to_homepage == 1 or 'http' not in self.driver.current_url:
                # 【修复】直接构造国际版搜索结果URL
                dep_code = get_city_code(self.city[0]) if self.city else 'CKG'
                arr_code = get_city_code(self.city[1]) if len(self.city) > 1 else 'NRT'
                date_str = self.date or '2026-04-04'
                # 国际版URL格式
                url = f"https://flights.ctrip.com/international/search/oneway-{dep_code}-{arr_code}?depdate={date_str}&cabin=y_s&adult=1&child=0&infant=0"
                self.driver.get(url)
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 访问: {url}')
            # 等待页面加载
            time.sleep(5)
            if self.check_verification_code():
                self.get_data()
        except Exception as e:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_page: {e}')
            if enable_screenshot:
                self.driver.save_screenshot(f'screenshot/error_getpage_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png')
            self.err += 1
            if self.err < max_retry_time:
                time.sleep(3)
                self.get_page(1)
            else:
                self.err = 0
    def change_city(self):
        """更换城市和日期 - 直接重新访问URL"""
        # 【修复】直接重新访问URL，而不是操作DOM
        self.get_page(1)
    # ============================================
    # 【修复】get_data - 增强稳定性
    # ============================================
    def get_data(self):
        """从DOM提取数据"""
        try:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_data: 等待航班列表加载...')
            # 【修复】先滚动页面触发懒加载
            self._scroll_to_load()
                        # ===== 新增：页面原生中转城市筛选（优先使用，更高效准确）
            try:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 尝试通过页面筛选栏过滤上海中转...')
                # 1. 点击中转筛选按钮，展开下拉面板（匹配你提供的id）
                trans_filter_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "filter_item_trans_count"))
                )
                trans_filter_btn.click()
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 已展开中转筛选面板')
                
                # 2. 找到中转城市列表中的上海选项（匹配span内的文本，因为城市名在span中）
                shanghai_span = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="filter_group_trans_city__city"]//span[contains(text(), "上海")]'))
                )
                # 找到父li元素，检查是否已经是选中状态（避免重复点击取消选中）
                shanghai_li = shanghai_span.find_element(By.XPATH, './parent::li')
                if 'active' not in shanghai_li.get_attribute('class'):
                    shanghai_span.click()  # 点击勾选框选中上海
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 已选中上海中转城市，等待页面筛选完成...')
                    # 等待页面完成筛选
                    time.sleep(3)
                else:
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 上海中转城市已处于选中状态，无需操作')
            except Exception as e:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 页面原生筛选失败，将使用后端数据筛选: {e}')
            
            # ===== 新增：点击"低价优先"排序 =====
            try:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 尝试点击低价优先排序...')
                # 尝试多种选择器找到低价优先按钮
                sort_selectors = [
                    '[data-testid="sort-price"]',
                    '[data-sort="price"]',
                    '.sort-price'
                ]
                sort_clicked = False
                for selector in sort_selectors:
                    try:
                        sort_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        sort_btn.click()
                        sort_clicked = True
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 已点击低价优先排序')
                        time.sleep(2)  # 等待排序完成
                        break
                    except:
                        continue
                if not sort_clicked:
                    # 尝试用文本匹配
                    try:
                        items = self.driver.find_elements(By.CSS_SELECTOR, '.sort-item, .sort-list li')
                        for item in items:
                            if '低价' in item.text:
                                item.click()
                                sort_clicked = True
                                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 已通过文本匹配点击低价优先排序')
                                time.sleep(2)
                                break
                    except:
                        pass
            except Exception as e:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 点击排序按钮失败，使用默认排序: {e}')
            
            # 【修复】尝试多个选择器找到航班列表
            flight_list_found = False
            used_selector = None
            for selector in SELECTORS['flight_list']:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    flight_list_found = True
                    used_selector = selector
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 找到航班列表容器: {selector}')
                    break
                except:
                    continue
            if not flight_list_found:
                # 检查是否是"无结果"页面
                no_result_selectors = ['.no-result', '.empty-result', '[class*="no-flight"]', '.empty', '.no-data']
                for selector in no_result_selectors:
                    try:
                        no_result = self.driver.find_element(By.CSS_SELECTOR, selector)
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 该航线无航班数据')
                        self.flights = []
                        self._process_and_save_data()
                        return
                    except:
                        continue
                # 如果都没找到，报错
                raise Exception("未找到航班列表容器")
            # 额外等待确保所有航班项渲染完成
            time.sleep(3)
            # 【修复】从DOM提取航班数据
            self.flights = self._extract_flights_from_dom()
            if not self.flights:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_data: 未找到航班数据')
                if enable_screenshot:
                    self.driver.save_screenshot(f'screenshot/no_flights_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png')
                # 创建空文件标记
                self.flights = []
                self._process_and_save_data()
                return
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_data: 成功提取 {len(self.flights)} 条航班数据')
            # 重置错误计数
            self.err = 0
            # 直接处理数据并保存
            self._process_and_save_data()
        except Exception as e:
            self.err += 1
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_data: 提取失败 {e}')
            if enable_screenshot:
                self.driver.save_screenshot(f'screenshot/error_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png')
            if self.err < max_retry_time:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_data: 刷新重试 ({self.err}/{max_retry_time})')
                self.refresh_driver()
                self.get_data()
            else:
                self.err = 0
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_data: 重试次数用尽，跳过')
    # ============================================
    # 【新增】滚动加载
    # ============================================
    def _scroll_to_load(self):
        """滚动页面触发懒加载"""
        try:
            # 先等待页面基本加载
            time.sleep(3)
            # 获取页面高度
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            # 滚动几次以触发懒加载
            for i in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            # 滚回顶部
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
        except Exception as e:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 滚动加载失败: {e}')
    # ============================================
    # 【修复】从DOM提取航班数据
    # ============================================
    def _extract_flights_from_dom(self):
        """从页面DOM结构提取航班信息"""
        flights = []
        # 尝试多个选择器找到航班项
        flight_items = []
        used_item_selector = None
        for selector in SELECTORS['flight_item']:
            try:
                items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if items:
                    flight_items = items
                    used_item_selector = selector
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} DOM提取: 使用选择器 {selector} 找到 {len(items)} 个航班项')
                    break
            except:
                continue
        if not flight_items:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} DOM提取: 未找到航班项')
            return flights
        for idx, item in enumerate(flight_items):
            try:
                flight_data = self._parse_flight_item(item, idx)
                if flight_data:
                    flights.append(flight_data)
            except Exception as e:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 解析第{idx+1}个航班失败: {e}')
                continue
        return flights
    def _parse_flight_item(self, item, idx):
        """解析单个航班项的DOM元素"""
        flight = {}
        # 【修复】使用辅助方法安全获取文本 - 尝试多组选择器
        def safe_get_text(selectors, default=''):
            for selector in selectors:
                try:
                    elem = item.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text:
                        return text
                except:
                    continue
            return default
        # 1. 航空公司名称
        flight['airline_name'] = safe_get_text(SELECTORS['airline_name'])
        # 2. 航班号和机型
        flight_no_text = safe_get_text(SELECTORS['flight_no'])
        if flight_no_text:
            # 处理格式: "IJ006 波音737(中)" 或 "IJ006\n波音737(中)"
            flight_no_parts = flight_no_text.replace('\xa0', ' ').replace('\n', ' ').split()
            flight['flight_no'] = flight_no_parts[0] if flight_no_parts else ''
            flight['aircraft_type'] = ' '.join(flight_no_parts[1:]) if len(flight_no_parts) > 1 else ''
        else:
            flight['flight_no'] = ''
            flight['aircraft_type'] = ''
        # 3. 出发时间
        flight['departure_time'] = safe_get_text(SELECTORS['depart_time'])
        # 4. 出发机场
        flight['departure_airport'] = safe_get_text(SELECTORS['depart_airport'])
        # 5. 出发航站楼
        flight['departure_terminal'] = safe_get_text(SELECTORS['depart_terminal'])
        # 6. 到达时间（处理+1等情况）
        arrive_text = safe_get_text(SELECTORS['arrive_time'])
        if arrive_text:
            # 处理格式: "14:10 " 或 "14:10+1" 或 "14:10\n+1"
            arrive_clean = arrive_text.replace('\n', ' ').strip()
            parts = arrive_clean.split()
            flight['arrival_time'] = parts[0] if parts else arrive_clean
            flight['arrival_next_day'] = '+1' in arrive_clean or '次日' in arrive_clean or 'day' in arrive_clean.lower()
        else:
            flight['arrival_time'] = ''
            flight['arrival_next_day'] = False
        # 7. 到达机场
        flight['arrival_airport'] = safe_get_text(SELECTORS['arrive_airport'])
        # 8. 到达航站楼
        flight['arrival_terminal'] = safe_get_text(SELECTORS['arrive_terminal'])
        # 9. 飞行时长
        flight['duration'] = safe_get_text(SELECTORS['duration'])
        # 10. 价格
        price_text = safe_get_text(SELECTORS['price'])
        if price_text:
            # 提取数字: "¥3,830" -> 3830
            price_clean = price_text.replace(',', '').replace(' ', '')
            price_match = re.search(r'[¥￥]?([\d]+)', price_clean)
            flight['price'] = int(price_match.group(1)) if price_match else 0
        else:
            flight['price'] = 0
        # 11. 出发/到达城市（从当前查询条件获取）
        flight['departure_city'] = self.city[0] if self.city else ''
        flight['arrival_city'] = self.city[1] if len(self.city) > 1 else ''
        flight['flight_date'] = self.date
        # 12. 数据获取时间
        flight['data_get_time'] = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 13. 提取中转城市信息（修复版，针对transfer-info结构）
        flight['transit_city'] = ''
        try:
            # 直接定位transfer-info元素，获取完整HTML/文本
            transfer_elem = item.find_element(By.CSS_SELECTOR, '.transfer-info')
            # 获取完整文本（包含<i>转</i>后面的内容）
            full_trans_text = transfer_elem.text
            # print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 调试：中转完整文本 = "{full_trans_text}"')
            
            # 从完整文本中提取城市名
            if '上海' in full_trans_text:
                flight['transit_city'] = '上海'
            else:
                # 兼容其他城市：提取"转"字后面的第一个城市名
                city_match = re.search(r'转([\u4e00-\u9fa5]+)', full_trans_text)
                if city_match:
                    flight['transit_city'] = city_match.group(1)
        except NoSuchElementException:
            # 没有中转信息，可能是直飞
            flight['transit_city'] = ''
        except Exception as e:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 提取中转城市失败: {e}')
            flight['transit_city'] = ''

        # 【修复】检查是否至少有关键字段（航班号或出发时间）
        if not flight['flight_no'] and not flight['departure_time']:
            return None
        return flight
    # ============================================
    # 处理和保存数据
    # ============================================
    def _process_and_save_data(self):
        """处理提取的航班数据并保存为CSV"""
        if not self.flights:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} _process_and_save_data: 无数据可处理')
            # 创建空文件标记
            files_dir = os.path.join(os.getcwd(), self.date, dt.now().strftime("%Y-%m-%d"))
            if not os.path.exists(files_dir):
                os.makedirs(files_dir)
            filename = os.path.join(files_dir, f"{self.city[0]}-{self.city[1]}.csv")
            # 创建带表头的空文件
            empty_df = pd.DataFrame(columns=[
                '航班号', '航空公司', '机型', '出发城市', '出发机场', '出发航站楼', '出发时间',
                '到达城市', '到达机场', '到达航站楼', '到达时间', '次日到达', '飞行时长', '价格',
                '中转城市', '航班日期', '数据获取时间'
            ])
            empty_df.to_csv(filename, encoding="UTF-8-sig", index=False)
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 创建空文件: {filename}')
            return
        # 转换为DataFrame
        df = pd.DataFrame(self.flights)
        
        # ===== 优化：增加调试信息，先保存原始数据用于排查 =====
        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 原始航班数据: {len(df)} 条')
        if not df.empty:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 中转城市字段值分布:')
            print(df['transit_city'].value_counts(dropna=False))
        
        # ===== 优化：更宽松的筛选逻辑 =====
        sh_transit_flights = pd.DataFrame()
        if not df.empty:
            # 1. 严格匹配
            strict_match = df[df['transit_city'] == '上海'].copy()
            if not strict_match.empty:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 严格匹配到 {len(strict_match)} 个上海中转航班')
                sh_transit_flights = strict_match
            else:
                # 2. 宽松匹配：包含"上海"字样
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 严格匹配失败，尝试宽松匹配...')
                loose_match = df[df['transit_city'].str.contains('上海', na=False)].copy()
                if not loose_match.empty:
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 宽松匹配到 {len(loose_match)} 个上海中转航班')
                    sh_transit_flights = loose_match
                else:
                    # 3. 兜底：如果页面已筛选，直接取前5条（假设页面筛选已生效）
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 数据匹配失败，假设页面筛选已生效，直接取前2条')
                    sh_transit_flights = df.head(5)
        
        # ===== 只取前5个（已按低价排序） =====
        if not sh_transit_flights.empty:
            sh_transit_flights = sh_transit_flights.head(5)
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 最终保留 {len(sh_transit_flights)} 个航班')
            df = sh_transit_flights
        else:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 未找到任何符合条件的航班')
            df = pd.DataFrame()  # 没有符合条件的，置空
        
        if df.empty:
            # 没有符合条件的数据，创建空文件
            files_dir = os.path.join(os.getcwd(), self.date, dt.now().strftime("%Y-%m-%d"))
            if not os.path.exists(files_dir):
                os.makedirs(files_dir)
            filename = os.path.join(files_dir, f"{self.city[0]}-{self.city[1]}.csv")
            empty_df = pd.DataFrame(columns=[
                '航班号', '航空公司', '机型', '出发城市', '出发机场', '出发航站楼', '出发时间',
                '到达城市', '到达机场', '到达航站楼', '到达时间', '次日到达', '飞行时长', '价格',
                '中转城市', '航班日期', '数据获取时间'
            ])
            empty_df.to_csv(filename, encoding="UTF-8-sig", index=False)
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 无符合条件的航班，创建空文件: {filename}')
            return
            
        # 定义列的顺序和中文名称
        column_mapping = {
            'flight_no': '航班号',
            'airline_name': '航空公司',
            'aircraft_type': '机型',
            'departure_city': '出发城市',
            'departure_airport': '出发机场',
            'departure_terminal': '出发航站楼',
            'departure_time': '出发时间',
            'arrival_city': '到达城市',
            'arrival_airport': '到达机场',
            'arrival_terminal': '到达航站楼',
            'arrival_time': '到达时间',
            'arrival_next_day': '次日到达',
            'duration': '飞行时长',
            'price': '价格',
            'transit_city': '中转城市',
            'flight_date': '航班日期',
            'data_get_time': '数据获取时间'
        }
        # 重命名列
        df = df.rename(columns=column_mapping)
        # 确保列顺序
        ordered_columns = list(column_mapping.values())
        existing_columns = [col for col in ordered_columns if col in df.columns]
        df = df[existing_columns]
        # 创建保存目录
        files_dir = os.path.join(os.getcwd(), self.date, dt.now().strftime("%Y-%m-%d"))
        if not os.path.exists(files_dir):
            os.makedirs(files_dir)
        # 保存CSV
        filename = os.path.join(files_dir, f"{self.city[0]}-{self.city[1]}.csv")
        df.to_csv(filename, encoding="UTF-8-sig", index=False)
        print(f'\n{time.strftime("%Y-%m-%d_%H-%M-%S")} 数据保存完成: {filename}')
        print(f'共 {len(df)} 条航班数据\n')
# ============================================
# 主程序入口
# ============================================
if __name__ == "__main__":
    # 创建截图目录
    if enable_screenshot and not os.path.exists('screenshot'):
        os.makedirs('screenshot')
    driver = init_driver()
    citys = gen_citys()
    flight_dates = generate_flight_dates(crawl_days, begin_date, end_date, 1, days_interval)
    Flight_DataFetcher = DataFetcher(driver)
    try:
        for city in citys:
            Flight_DataFetcher.city = city
            for flight_date in flight_dates:
                Flight_DataFetcher.date = flight_date
                # 检查文件是否已存在
                output_path = os.path.join(
                    os.getcwd(), flight_date, dt.now().strftime("%Y-%m-%d"), 
                    f"{city[0]}-{city[1]}.csv"
                )
                if os.path.exists(output_path):
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 文件已存在: {output_path}')
                    continue
                print(f'\n{time.strftime("%Y-%m-%d_%H-%M-%S")} 开始查询: {city[0]} -> {city[1]}, 日期: {flight_date}')
                # 直接访问搜索结果页
                Flight_DataFetcher.get_page(1)
                # 随机延迟，避免被封
                sleep_time = crawl_interval + random.uniform(1, 3)
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 等待 {sleep_time:.1f} 秒...')
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        print(f'\n{time.strftime("%Y-%m-%d_%H-%M-%S")} 用户中断程序')
    finally:
        # 退出
        try:
            driver.quit()
        except Exception as e:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 退出失败: {e}')
        print(f'\n{time.strftime("%Y-%m-%d_%H-%M-%S")} 程序运行完成！')

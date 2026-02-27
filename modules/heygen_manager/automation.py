import asyncio
import os
import time
from datetime import datetime
from playwright.async_api import async_playwright

class HeyGenAutomation:
    def __init__(self, instance_id=0, log_callback=None, status_callback=None):
        """
        :param instance_id: 实例唯一 ID
        :param log_callback: UI 日志回调 函数 (str)
        :param status_callback: UI 状态回调 函数 (id, status, url, action)
        """
        self.instance_id = instance_id
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.is_running = False

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] [实例#{self.instance_id}] {message}"
        print(formatted_message)
        if self.log_callback:
            self.log_callback(formatted_message)

    def update_status(self, status=None, url=None, action=None):
        if self.status_callback:
            self.status_callback(self.instance_id, status, url, action)


    async def start_browser(self, headless=False, storage_state_path=None):
        self.log(f"🚀 正在启动 Playwright 浏览器...")
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=["--start-maximized"]
            )
            
            # Load storage state if provided and exists
            context_args = {"no_viewport": True}
            if storage_state_path and os.path.exists(storage_state_path):
                self.log(f"📂 加载会话备份: {os.path.basename(storage_state_path)}")
                context_args["storage_state"] = storage_state_path
                
            self.context = await self.browser.new_context(**context_args)
            self.page = await self.context.new_page()
            self.log("✅ 浏览器启动成功")
            
            # 自动跳转至 HeyGen
            await self.navigate("https://app.heygen.com/")
            self.is_running = True
        except Exception as e:
            self.log(f"❌ 浏览器启动失败: {str(e)}")
            await self.close()

    async def close(self):
        self.log("🛑 正在关闭浏览器...")
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            self.log(f"⚠️ 关闭过程中的小异常: {e}")
            
        self.is_running = False
        self.log("🏁 浏览器已关闭")

    async def wait_and_click(self, selector, description, timeout=30000):
        self.log(f"🔍 正在寻找并点击: {description} ({selector})")
        try:
            # 等待元素可见并可用
            element = await self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            if element:
                # 滚动到中心并高亮一下（可选，有助于调试）
                await element.scroll_into_view_if_needed()
                # 执行点击
                await element.click()
                self.log(f"✅ 成功点击: {description}")
                return True
            else:
                self.log(f"⚠️ 未找到元素: {description}")
                return False
        except Exception as e:
            self.log(f"❌ 点击失败: {description}. 错误: {str(e)}")
            # 自动截图保存
            await self.capture_error(f"click_fail_{description}")
            return False

    async def wait_and_type(self, selector, text, description, timeout=30000):
        self.log(f"⌨️ 正在输入: {description} (内容: {text})")
        try:
            element = await self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            if element:
                await element.fill(text)
                self.log(f"✅ 成功输入: {description}")
                return True
            else:
                self.log(f"⚠️ 未找到元素: {description}")
                return False
        except Exception as e:
            self.log(f"❌ 输入失败: {description}. 错误: {str(e)}")
            await self.capture_error(f"type_fail_{description}")
            return False

    async def upload_file(self, selector, file_path, description, timeout=30000):
        self.log(f"📤 正在上传文件: {description} (路径: {file_path})")
        if not os.path.exists(file_path):
            self.log(f"❌ 文件不存在: {file_path}")
            return False
        
        try:
            # Playwright 直接支持 set_input_files
            await self.page.set_input_files(selector, file_path, timeout=timeout)
            self.log(f"✅ 成功上传: {description}")
            return True
        except Exception as e:
            self.log(f"❌ 上传失败: {description}. 尝试模拟点击上传...")
            # 如果 set_input_files 失败，可能需要先点击再监听 filechooser
            try:
                async with self.page.expect_file_chooser() as fc_info:
                    await self.page.click(selector)
                file_chooser = await fc_info.value
                await file_chooser.set_files(file_path)
                self.log(f"✅ 模拟上传成功: {description}")
                return True
            except Exception as e2:
                self.log(f"❌ 模拟上传也失败: {str(e2)}")
                await self.capture_error(f"upload_fail_{description}")
                return False

    async def capture_error(self, name):
        if not self.page: return
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_{name}_{timestamp}.png"
            # 确保 logs 目录存在
            os.makedirs("logs/screenshots", exist_ok=True)
            path = os.path.join("logs/screenshots", filename)
            await self.page.screenshot(path=path)
            self.log(f"📸 错误截图已保存: {path}")
        except Exception as e:
            self.log(f"❌ 截图失败: {str(e)}")

    async def navigate(self, url):
        self.log(f"🌐 正在跳转: {url}")
        self.update_status(url=url, action="跳转中")
        try:
            # 策略调整：改用 'domcontentloaded' 或 'commit'，因为 'networkidle' 在重负载页面下极易超时
            await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self.log("✅ 页面基础加载完成 (DOM Ready)")
            self.update_status(status="在线", action="页面加载完成")
            
            # 额外给点缓冲时间，但不死等网络静默
            await asyncio.sleep(2)
            
            return True
        except Exception as e:
            # 补救逻辑：检查当前 URL 是否已经包含目标路径，如果是，则视为“带病运行”成功
            current_url = self.page.url if self.page else ""
            if url.split("?")[0] in current_url:
                self.log(f"⚠️ 跳转触发超时，但检测到已处于目标页面 ({current_url})，将尝试继续执行。")
                self.update_status(status="在线", url=current_url, action="加载超时(已就绪)")
                return True
            
            self.log(f"❌ 跳转彻底失败: {str(e)}")
            self.update_status(status="异常", action="跳转失败")
            return False

    # --- 复合业务流程 (供 UI 直接调用) ---

    async def login_via_email(self, email):
        self.log(f"🔑 正在尝试通过邮箱登录: {email}")
        # 根据录制代码，登录入口可能在 auth.heygen.com
        await self.navigate("https://auth.heygen.com/")
        
        try:
            # 1. 点击 "Continue with email" 按钮
            await self.page.get_by_role("button", name="Continue with email").click()
            await asyncio.sleep(1)

            # 2. 填写邮箱
            self.log(f"⌨️ 正在输入: {email}")
            await self.page.get_by_role("textbox", name="Enter your email").fill(email)
            
            # 3. 点击 "Send link" 按钮
            await self.page.get_by_role("button", name="Send link").click()
            self.log("✅ 登录链接已发送")
            
            return True
        except Exception as e:
            self.log(f"❌ 邮件登录步骤失败: {e}")
            await self.capture_error("login_fail")
            return False

    async def login_via_magic_link(self, magic_link):
        self.log(f"🔗 正在通过魔力链接登录...")
        return await self.navigate(magic_link)

    async def onboarding_flow(self):
        """自动化新手引导流程 (最新的问卷填写逻辑)"""
        self.log("🚀 开始执行最新问卷填单流程...")
        try:
            # 1. 跳转到 onboarding 页面 (如果不在的话)
            if "onboarding" not in self.page.url:
                await self.navigate("https://app.heygen.com/onboarding")
            
            import re
            
            # 2. 第一步: Social Media -> Continue
            self.log("填单(1/4): 选择 Social Media")
            await self.page.locator("div").filter(has_text=re.compile(r"^Social Media$")).first.click()
            await asyncio.sleep(0.5)
            await self.page.get_by_role("button", name="Continue").click()
            await asyncio.sleep(1)

            # 3. 第二步: Marketing -> Continue
            self.log("填单(2/4): 选择 Marketing")
            await self.page.locator("div").filter(has_text=re.compile(r"^Marketing$")).first.click()
            await asyncio.sleep(0.5)
            await self.page.get_by_role("button", name="Continue").click()
            await asyncio.sleep(1)

            # 4. 第三步: Independent work -> Submit
            self.log("填单(3/4): 选择 Independent work")
            await self.page.locator("div").filter(has_text=re.compile(r"^I run my own business or work independently$")).first.click()
            await asyncio.sleep(0.5)
            await self.page.get_by_role("button", name="Submit").click()
            await asyncio.sleep(1)

            # 5. 第四步: Choose Free
            self.log("填单(4/4): 选择 Free Plan")
            await self.page.get_by_role("button", name="Choose Free").click()
            
            self.log("✅ 问卷填单流程全部完成！")
            return True
        except Exception as e:
            self.log(f"❌ 填单流程失败: {e}")
            await self.capture_error("onboarding_fail")
            return False


    async def download_video_flow(self):
        """9. 下载流程"""
        await self.navigate("https://app.heygen.com/projects")
        
        # page.get_by_text("Download").click()
        # 这可能是列表页的下载图标或文字
        await self.wait_and_click('text="Download"', "列表页 Download")

        # 处理下载事件
        self.log("⬇️ 等待下载触发...")
        try:
            async with self.page.expect_download(timeout=60000) as download_info:
                # page.get_by_role("button", name="Download").click()
                # 弹窗里的确认下载
                await self.page.get_by_role("button", name="Download").click()
            
            download = await download_info.value
            save_path = os.path.join("downloads", download.suggested_filename)
            os.makedirs("downloads", exist_ok=True)
            await download.save_as(save_path)
            self.log(f"✅ 文件已下载: {save_path}")
            return save_path
        except Exception as e:
            self.log(f"❌ 下载失败: {e}")
            return None


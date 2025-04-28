import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
import json
import threading
import time
import math

class OllamaRemoteGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ollama 远程 GUI 工具")
        self.root.geometry("800x700")

        self.ollama_base_url = ""
        self.available_models = []
        self.selected_model = None
        self._stop_download_thread = False # Flag to signal download thread to stop (optional)

        # Variables for speed calculation
        self._last_completed_bytes = 0
        self._last_timestamp = 0


        # --- Connection Frame ---
        conn_frame = ttk.LabelFrame(root, text="Ollama 服务器连接")
        conn_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        ttk.Label(conn_frame, text="服务器 IP:").grid(row=0, column=0, padx=5, pady=5)
        self.ip_entry = ttk.Entry(conn_frame, width=20)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)
        self.ip_entry.insert(0, "127.0.0.1") # Default or replace with your server IP

        ttk.Label(conn_frame, text="端口:").grid(row=0, column=2, padx=5, pady=5)
        self.port_entry = ttk.Entry(conn_frame, width=10)
        self.port_entry.grid(row=0, column=3, padx=5, pady=5)
        self.port_entry.insert(0, "11434") # Default Ollama port

        self.connect_button = ttk.Button(conn_frame, text="连接并加载模型", command=self.connect_and_load_models)
        self.connect_button.grid(row=0, column=4, padx=5, pady=5)

        self.status_label = ttk.Label(conn_frame, text="状态: 未连接", foreground="red")
        self.status_label.grid(row=0, column=5, padx=5, pady=5, sticky="w")

        # Configure grid columns to expand
        conn_frame.columnconfigure(1, weight=1)
        conn_frame.columnconfigure(5, weight=1)


        # --- Model Selection Frame ---
        model_frame = ttk.LabelFrame(root, text="模型选择")
        model_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        ttk.Label(model_frame, text="可用模型:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.model_select_var = tk.StringVar()
        self.model_dropdown = ttk.OptionMenu(model_frame, self.model_select_var, "", *["加载中..."])
        self.model_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.model_dropdown['menu'].delete(0) # Remove the "Loading..." placeholder

        self.model_select_var.trace_add("write", self.on_model_selected)

        ttk.Label(model_frame, text="已选模型:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.selected_model_label = ttk.Label(model_frame, text="无")
        self.selected_model_label.grid(row=1, column=1, padx=0, pady=5, sticky="w") # Adjusted padx

        # 添加复制按钮
        self.copy_button = ttk.Button(model_frame, text="复制", command=self.copy_selected_model, width=6, state='disabled') # Added copy button
        self.copy_button.grid(row=1, column=2, padx=5, pady=5) # Placed in the next column

        model_frame.columnconfigure(1, weight=1)


        # --- Chat Frame ---
        chat_frame = ttk.LabelFrame(root, text="聊天")
        chat_frame.grid(row=1, column=1, padx=10, pady=5, sticky="nsew", rowspan=2)

        ttk.Label(chat_frame, text="聊天历史:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.chat_history_text = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, width=60, height=25, state='disabled')
        self.chat_history_text.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        ttk.Label(chat_frame, text="你的提示词:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.prompt_entry = ttk.Entry(chat_frame, width=60)
        self.prompt_entry.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        self.prompt_entry.bind("<Return>", lambda event=None: self.send_message()) # Allow sending with Enter key

        self.send_button = ttk.Button(chat_frame, text="发送", command=self.send_message, state='disabled')
        self.send_button.grid(row=4, column=0, padx=5, pady=5)

        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(1, weight=1)


        # --- Model Management Frame ---
        manage_frame = ttk.LabelFrame(root, text="模型管理")
        manage_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        # Delete Model
        ttk.Label(manage_frame, text="要删除的模型:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.delete_model_entry = ttk.Entry(manage_frame, width=30)
        self.delete_model_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.delete_button = ttk.Button(manage_frame, text="删除模型", command=self.delete_model, state='disabled')
        self.delete_button.grid(row=0, column=2, padx=5, pady=5)

        # Download Model
        ttk.Label(manage_frame, text="要下载的模型:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.pull_model_entry = ttk.Entry(manage_frame, width=30)
        self.pull_model_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.pull_button = ttk.Button(manage_frame, text="下载模型", command=self.pull_model, state='disabled')
        self.pull_button.grid(row=1, column=2, padx=5, pady=5)

        # Download Status, Progress Bar, and Speed
        self.download_status_label = ttk.Label(manage_frame, text="", foreground="blue")
        self.download_status_label.grid(row=2, column=0, columnspan=3, padx=5, pady=2, sticky="ew")
        self.download_status_label.grid_remove() # Hide initially

        self.progress_bar = ttk.Progressbar(manage_frame, orient="horizontal", length=200, mode="determinate")
        self.progress_bar.grid(row=3, column=0, columnspan=3, padx=5, pady=2, sticky="ew")
        self.progress_bar.grid_remove() # Hide initially

        self.estimated_speed_label = ttk.Label(manage_frame, text="", foreground="gray") # Added speed label
        self.estimated_speed_label.grid(row=4, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        self.estimated_speed_label.grid_remove() # Hide initially


        manage_frame.columnconfigure(1, weight=1)
        manage_frame.columnconfigure(2, weight=0) # Button column

        # --- Final Layout Configuration ---
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=0) # Model selection row doesn't need extra height
        root.rowconfigure(2, weight=1) # Chat row gets most of the height

        self.set_controls_state('disabled') # Disable controls until connected
        self.copy_button.config(state='disabled') # Ensure copy button is disabled initially

        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)


    def on_closing(self):
        """Handle window closing, potentially stopping download thread."""
        self._stop_download_thread = True # Signal the thread to stop
        # Give the thread a moment to check the flag and exit gracefully
        time.sleep(0.05) # A very small delay might help
        self.root.destroy() # Close the window


    def set_controls_state(self, state):
        """Helper to enable/disable controls based on connection status."""
        self.model_dropdown.config(state=state)
        self.prompt_entry.config(state=state)
        self.send_button.config(state=state)
        self.delete_model_entry.config(state=state)
        self.delete_button.config(state=state)
        self.pull_model_entry.config(state=state)
        # self.pull_button.config(state=state) # Pull button state managed separately during download
        # Leave IP/Port/Connect button enabled
        # Copy button state managed in on_model_selected


    def update_status(self, message, is_error=False):
        """Update the main status label."""
        self.status_label.config(text=f"状态: {message}", foreground="red" if is_error else "green")
        self.root.update_idletasks() # Update GUI immediately

    def update_download_status(self, message="", progress_value=0, progress_max=100, speed_text="", is_error=False, hide=False):
        """Update the download status label, progress bar, and speed label."""
        # Schedule the actual update on the main thread using after
        self.root.after(0, self._update_download_status_gui, message, progress_value, progress_max, speed_text, is_error, hide)


    def _update_download_status_gui(self, message, progress_value, progress_max, speed_text, is_error, hide):
        """Thread-safe GUI update for download status."""
        if hide:
            self.download_status_label.grid_remove()
            self.progress_bar.grid_remove()
            self.estimated_speed_label.grid_remove()
            self.progress_bar['value'] = 0
            self.progress_bar['maximum'] = 100
            self.download_status_label.config(text="", foreground="blue")
            self.estimated_speed_label.config(text="", foreground="gray")
        else:
            self.download_status_label.grid()
            self.progress_bar.grid()
            self.estimated_speed_label.grid()
            self.download_status_label.config(text=message, foreground="red" if is_error else "blue")
            # Ensure max > 0 to avoid errors
            self.progress_bar['maximum'] = max(1, progress_max)
            # Ensure value is within bounds [0, max]
            self.progress_bar['value'] = max(0, min(progress_value, progress_max))
            self.estimated_speed_label.config(text=speed_text, foreground="gray")


    def format_bytes(self, byte_count):
        """Formats bytes into human-readable string (B, KB, MB, GB)."""
        if byte_count is None:
            return "N/A"
        if byte_count == 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        i = int(math.floor(math.log(byte_count, 1024)))
        i = max(0, min(i, len(units) - 1)) # Ensure index is within bounds
        p = math.pow(1024, i)
        return f"{byte_count / p:.2f} {units[i]}"


    def add_message(self, sender, message):
        """Add a message to the chat history text area."""
        sender_display = sender
        if sender == "You":
             sender_display = "你"
        elif sender == "Error":
             sender_display = "错误"

        # Schedule GUI update on the main thread
        self.root.after(0, self._add_message_gui, sender_display, message)

    def _add_message_gui(self, sender_display, message):
        """Thread-safe GUI update for adding chat message."""
        self.chat_history_text.config(state='normal')
        self.chat_history_text.insert(tk.END, f"<{sender_display}>: {message}\n\n")
        self.chat_history_text.see(tk.END) # Scroll to the bottom
        self.chat_history_text.config(state='disabled')


    def connect_and_load_models(self):
        """Attempt to connect to Ollama and load available models."""
        ip = self.ip_entry.get()
        port = self.port_entry.get()

        if not ip or not port:
            messagebox.showwarning("输入错误", "请输入 IP 和端口。")
            return

        self.ollama_base_url = f"http://{ip}:{port}"
        self.update_status(f"正在连接到 {self.ollama_base_url}...", False)
        self.set_controls_state('disabled') # Disable controls during connection attempt
        self.pull_button.config(state='disabled') # Disable pull button during connection
        self.copy_button.config(state='disabled') # Disable copy button during connection
        self.update_download_status(hide=True) # Hide download status on new connection attempt

        try:
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5) # Add a timeout
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            self.available_models = [model['name'] for model in response.json().get('models', [])]

            # Update the OptionMenu with available models
            menu = self.model_dropdown['menu']
            menu.delete(0, 'end') # Clear existing options
            if self.available_models:
                for model_name in self.available_models:
                    menu.add_command(label=model_name, command=lambda value=model_name: self.model_select_var.set(value))
                # Select the first model by default if available
                self.model_select_var.set(self.available_models[0]) if self.available_models else self.model_select_var.set("")
            else:
                 menu.add_command(label="未找到模型", command=None)
                 self.model_select_var.set("") # Clear selection if no models

            self.update_status("已连接，模型加载成功。", False)
            self.set_controls_state('normal') # Enable controls
            self.pull_button.config(state='normal') # Re-enable pull button on successful connection
            # Copy button state is handled in on_model_selected

        except requests.exceptions.ConnectionError:
            self.update_status("连接失败。", True)
            messagebox.showerror("连接错误", f"无法连接到 {self.ollama_base_url}\n\n请检查 IP、端口、Ollama 服务和防火墙设置。")
            self.set_controls_state('disabled')
            self.pull_button.config(state='disabled') # Disable pull button on connection failure
            self.copy_button.config(state='disabled') # Disable copy button on connection failure
            self.model_dropdown['menu'].delete(0, 'end')
            self.model_dropdown['menu'].add_command(label="连接失败", command=None)
            self.model_select_var.set("")
            self.selected_model_label.config(text="无")
            self.ollama_base_url = "" # Clear base URL on failure

        except requests.exceptions.Timeout:
             self.update_status("连接超时。", True)
             messagebox.showerror("连接错误", f"连接到 {self.ollama_base_url} 超时。")
             self.set_controls_state('disabled')
             self.pull_button.config(state='disabled') # Disable pull button on connection failure
             self.copy_button.config(state='disabled') # Disable copy button on connection failure
             self.model_dropdown['menu'].delete(0, 'end')
             self.model_dropdown['menu'].add_command(label="连接失败", command=None)
             self.model_select_var.set("")
             self.selected_model_label.config(text="无")
             self.ollama_base_url = ""

        except requests.exceptions.RequestException as e:
            self.update_status("发生错误。", True)
            messagebox.showerror("请求错误", f"发生错误: {e}")
            self.set_controls_state('disabled')
            self.pull_button.config(state='disabled') # Disable pull button on connection failure
            self.copy_button.config(state='disabled') # Disable copy button on connection failure
            self.model_dropdown['menu'].delete(0, 'end')
            self.model_dropdown['menu'].add_command(label="连接失败", command=None)
            self.model_select_var.set("")
            self.selected_model_label.config(text="无")
            self.ollama_base_url = ""

        except json.JSONDecodeError:
             self.update_status("服务器响应无效。", True)
             messagebox.showerror("响应错误", f"无法解析来自 {self.ollama_base_url}/api/tags 的 JSON 响应。 这是 Ollama 服务器吗?")
             self.set_controls_state('disabled')
             self.pull_button.config(state='disabled') # Disable pull button on connection failure
             self.copy_button.config(state='disabled') # Disable copy button on connection failure
             self.model_dropdown['menu'].delete(0, 'end')
             self.model_dropdown['menu'].add_command(label="连接失败", command=None)
             self.model_select_var.set("")
             self.selected_model_label.config(text="无")
             self.ollama_base_url = ""


    def on_model_selected(self, *args):
        """Update the selected model label and enable/disable controls."""
        self.selected_model = self.model_select_var.get()
        self.selected_model_label.config(text=self.selected_model if self.selected_model else "无")

        # Enable send and copy buttons only if a model is selected and connected
        if self.selected_model and self.ollama_base_url:
             self.send_button.config(state='normal')
             self.copy_button.config(state='normal') # Enable copy button
        else:
             self.send_button.config(state='disabled')
             self.copy_button.config(state='disabled') # Disable copy button


    def copy_selected_model(self):
        """Copies the selected model name to the clipboard."""
        if self.selected_model:
            try:
                self.root.clipboard_clear() # Clear clipboard
                self.root.clipboard_append(self.selected_model) # Append model name
                self.update_status(f"模型名称已复制：{self.selected_model}", False) # Feedback
            except Exception as e:
                self.update_status(f"复制到剪贴板失败: {e}", True) # Error feedback
                messagebox.showerror("复制错误", f"复制到剪贴板失败: {e}")
        else:
            self.update_status("没有选择的模型可复制。", True) # Feedback
            messagebox.showwarning("操作无效", "没有选择的模型可复制。")


    def send_message(self):
        """Send a prompt to the selected model."""
        if not self.ollama_base_url or not self.selected_model:
            messagebox.showwarning("需要操作", "请连接到 Ollama 并选择一个模型。")
            return

        prompt = self.prompt_entry.get().strip()
        if not prompt:
            messagebox.showwarning("输入错误", "请输入提示词。")
            return

        self.add_message("You", prompt)
        self.prompt_entry.delete(0, tk.END)
        self.update_status("正在发送提示词...", False)
        self.send_button.config(state='disabled') # Disable send during processing

        # Use threading to avoid freezing the GUI during the API call
        thread = threading.Thread(target=self._send_message_thread, args=(prompt,))
        thread.start()


    def _send_message_thread(self, prompt):
         """Internal method to handle sending message in a separate thread."""
         try:
            payload = {
                "model": self.selected_model,
                "prompt": prompt,
                "stream": False # For simplicity, not handling streaming in this basic example
            }
            response = requests.post(f"{self.ollama_base_url}/api/generate", json=payload, timeout=120) # Increased timeout for inference
            response.raise_for_status()

            result = response.json()
            model_response = result.get("response", "结果中未找到 'response' 键。")

            # Update GUI from the main thread using after()
            self.add_message(self.selected_model, model_response) # add_message handles its own after
            self.update_status("就绪", False) # Positional args

         except requests.exceptions.RequestException as e:
            error_message = f"发送消息错误: {e}"
            self.add_message("Error", error_message) # add_message handles its own after
            self.update_status("聊天过程中发生错误。", True) # Positional args
            self.root.after(0, messagebox.showerror, "请求错误", error_message) # messagebox needs after

         except json.JSONDecodeError:
            error_message = f"解析模型响应的 JSON 错误。"
            self.add_message("Error", error_message) # add_message handles its own after
            self.update_status("聊天过程中发生错误。", True) # Positional args
            self.root.after(0, messagebox.showerror, "响应错误", error_message) # messagebox needs after

         finally:
             # Re-enable the send button in the main thread
             self.root.after(0, lambda: self.send_button.config(state='normal')) # Use lambda


    def delete_model(self):
        """Delete a specified model from the server."""
        if not self.ollama_base_url:
            messagebox.showwarning("需要操作", "请连接到 Ollama。")
            return

        model_to_delete = self.delete_model_entry.get().strip()
        if not model_to_delete:
            messagebox.showwarning("输入错误", "请输入要删除的模型名称。")
            return

        # Simple confirmation
        if not messagebox.askyesno("确认删除", f"确定要删除模型 '{model_to_delete}' 吗？"):
            return

        self.update_status(f"正在删除模型 '{model_to_delete}'...", False) # Positional args
        self.set_controls_state('disabled') # Disable controls during operation
        self.pull_button.config(state='disabled') # Disable pull button
        self.copy_button.config(state='disabled') # Disable copy button
        self.update_download_status(hide=True) # Hide download status

        try:
            payload = {"name": model_to_delete}
            response = requests.delete(f"{self.ollama_base_url}/api/delete", json=payload, timeout=30)
            response.raise_for_status() # Raise an exception for bad status codes

            self.update_status(f"模型 '{model_to_delete}' 删除成功。", False) # Positional args
            self.delete_model_entry.delete(0, tk.END)
            # Reload models after deletion - this includes re-enabling buttons on success
            self.connect_and_load_models()

        except requests.exceptions.RequestException as e:
            self.update_status("删除模型错误。", True) # Positional args
            messagebox.showerror("删除错误", f"删除模型 '{model_to_delete}' 错误: {e}")
            self.set_controls_state('normal')
            self.pull_button.config(state='normal')
            self.copy_button.config(state='normal') # Re-enable copy button on error
            self.on_model_selected() # Re-evaluate copy button state based on model selection


    def pull_model(self):
        """Initiate download (pull) of a specified model."""
        if not self.ollama_base_url:
            messagebox.showwarning("需要操作", "请连接到 Ollama。")
            return

        model_to_pull = self.pull_model_entry.get().strip()
        if not model_to_pull:
            messagebox.showwarning("输入错误", "请输入要下载的模型名称。")
            return

        # Reset and show download status
        # Use positional args for update_download_status
        self.update_download_status(f"准备下载模型 '{model_to_pull}'...", 0, 100, "", False, False)
        self.update_status("下载中...", False) # Positional args
        self.set_controls_state('disabled') # Disable controls during operation
        self.pull_button.config(state='disabled') # Explicitly disable pull button
        self.copy_button.config(state='disabled') # Disable copy button during download

        # Reset speed calculation variables
        self._last_completed_bytes = 0
        self._last_timestamp = time.time()

        # Use threading to handle the streaming download
        self._stop_download_thread = False # Reset stop flag
        thread = threading.Thread(target=self._pull_model_thread, args=(model_to_pull,))
        thread.start()


    def _pull_model_thread(self, model_name):
         """Internal method to handle pulling model with progress in a separate thread."""
         try:
            payload = {
                "name": model_name,
                "stream": True
            }
            # Use stream=True to read the response incrementally
            with requests.post(f"{self.ollama_base_url}/api/pull", json=payload, timeout=7200, stream=True) as response: # Increased timeout further for very large models
                 response.raise_for_status()

                 # Read the stream line by line
                 for line in response.iter_lines():
                     if self._stop_download_thread: # Check stop flag
                         break
                     if line:
                        try:
                            data = json.loads(line)
                            status = data.get('status', '未知状态')
                            total = data.get('total')
                            completed = data.get('completed')

                            current_time = time.time()
                            speed_text_display = "" # Separate variable for display

                            # Calculate speed if we have numerical progress and time has passed
                            # Ensure completed is a number before calculating speed
                            if isinstance(completed, int) and completed > self._last_completed_bytes and current_time > self._last_timestamp:
                                delta_bytes = completed - self._last_completed_bytes
                                delta_time = current_time - self._last_timestamp
                                if delta_time > 0:
                                    bytes_per_second = delta_bytes / delta_time
                                    speed_text_display = f"速度: {self.format_bytes(bytes_per_second)}/秒" # Format speed
                                    # Update speed label directly via after for responsiveness
                                    # Use lambda to pass keyword argument 'text' to config
                                    self.root.after(0, lambda text=speed_text_display: self.estimated_speed_label.config(text=text))

                                self._last_completed_bytes = completed
                                self._last_timestamp = current_time
                            # else:
                                # If no speed calculated in this update, we could potentially get the last speed
                                # text from the label itself, but it adds complexity and potential race conditions.
                                # Passing an empty string in update_download_status when no new speed is calculated is acceptable.


                            # Schedule GUI update for status and progress bar
                            # Use positional arguments for after
                            self.update_download_status(
                                f"{status} ({self.format_bytes(completed)} / {self.format_bytes(total)})",
                                completed if isinstance(completed, int) else 0, # Ensure integer for value
                                total if isinstance(total, int) else 100,      # Ensure integer for max, default to 100 if not available
                                speed_text_display, False, False) # Pass the display variable


                        except json.JSONDecodeError:
                             print(f"Warning: Could not decode JSON line: {line}")
                             # Get last speed text to pass it along for status update only
                             last_speed_text = self.estimated_speed_label.cget("text") if self.estimated_speed_label.winfo_exists() else "" # Check widget exists
                             # Update status text with error line, keep last calculated speed
                             # Use positional arguments for after
                             self.update_download_status(
                                f"接收到非JSON数据: {line.decode('utf-8', 'ignore')}",
                                self.progress_bar['value'], self.progress_bar['maximum'], last_speed_text, False, False)


            # Check if loop was broken by stop flag
            if self._stop_download_thread:
                 # Use positional arguments for after
                 self.update_status("下载已取消。", True)
                 self.update_download_status("", 0, 100, "", False, True) # Positional args for hide
            else:
                 # Download finished successfully (response loop completed)
                 # Use positional arguments for after
                 self.update_download_status("下载完成。", 100, 100, "速度: N/A", False, False)
                 self.update_status("下载完成。", False)
                 # Use positional arguments for after
                 self.root.after(5000, self.update_download_status, "", 0, 100, "", False, True) # Positional args for hide
                 # Schedule reloading models after a short delay
                 self.root.after(2000, self.connect_and_load_models)


         except requests.exceptions.RequestException as e:
            error_message = f"下载模型 '{model_name}' 错误: {e}"
            print(error_message) # Print to console for debugging
            last_speed_text = self.estimated_speed_label.cget("text") if self.estimated_speed_label.winfo_exists() else "" # Get current speed text
            # Use positional arguments for after
            self.update_download_status(error_message, self.progress_bar['value'], self.progress_bar['maximum'], last_speed_text, True, False)
            self.update_status("下载失败。", True)
            # Keep download status visible until user connects again or hides it


         finally:
             # Re-enable controls in the main thread
             self.root.after(0, self.set_controls_state, 'normal')
             self.root.after(0, lambda: self.pull_button.config(state='normal')) # Use lambda
             # Re-enable copy button based on selection after download finishes/errors
             self.root.after(0, self.on_model_selected)


if __name__ == "__main__":
    root = tk.Tk()
    app = OllamaRemoteGUI(root)
    root.mainloop()
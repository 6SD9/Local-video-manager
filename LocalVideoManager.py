import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
from PIL import Image, ImageTk
import re
import copy
import tkinter.font as tkfont
import random
from datetime import datetime
from collections import Counter, defaultdict
import threading
import io
import ctypes

# 注意：这个脚本需要安装 Pillow 库（pip install pillow）。
# PotPlayer 的路径需要根据你的安装位置调整，如果 PotPlayer 已添加到 PATH，可以直接用 'PotPlayerMini64.exe' 或类似。
# 视频文件扩展名可以根据需要扩展。
# 假设文件名格式： "名称[标签1,标签2]{演员1,演员2}(系列)~发行时间@星级%特征码.ext"，如 "My Video[Action,Comedy]{Actor1,Actor2}(Season1)~2023-01-01@3%code.mp4"
# 星级为1-5整数，如果无则默认1。
# 如果无括号或大括号，则相应为空。
# 封面图片：同路径下 "名称.jpg" 或 "名称.png"，如果不存在则用默认占位。

POTPLAYER_PATH = r"D:\APP\PotPlayer\PotPlayerMini64.exe"  # 替换为你的 PotPlayer 路径
VIDEO_EXTENSIONS = (".mp4", ".avi", ".mkv", ".mov", ".wmv")  # 支持的视频格式


class VideoBrowser:
    def __init__(self, root):
        self.root = root
        self.root.title("本地视频浏览器")
        self.root.geometry("1200x800")

        self.video_dir = None
        self.videos = (
            []
        )  # 存储视频信息：(路径, 名称, 标签列表, 演员列表, 系列, 发行时间, 星级, 缩略图路径, 特征码)
        self.all_tags = set()  # 所有独特标签
        self.all_actors = set()  # 所有独特演员
        self.all_series = set()  # 所有独特系列
        self.all_ratings = set()  # 所有独特星级
        self.actor_counts = Counter()
        self.selected_tags = set()  # 用户选择的标签
        self.selected_actors = set()  # 用户选择的演员
        self.selected_series = set()  # 用户选择的系列
        self.selected_ratings = set()  # 用户选择的星级
        self.search_keyword = ""  # 搜索关键词
        self.grid_size = 330  # 初始网格尺寸（宽度），高度将基于此计算
        self.font_size = 12
        self.history = []  # 筛选历史栈
        self.redo_stack = []  # 重做栈
        self.last_canvas_width = 0
        self.batch_mode = False
        self.selected_videos = set()  # 选中的视频路径
        self.potplayer_path = POTPLAYER_PATH
        self.show_thumbnails = tk.BooleanVar(value=True)
        self.current_displayed = None  # 用于临时显示相似视频等
        self.filtered_videos = []
        self.rendered_count = 0
        self.current_row = 0
        self.cols = 1
        self.batch_size = 24  # 减小批量大小，以实现“少量、多次”
        self.loading_scheduled = False
        self.scroll_threshold = 0.6  # 降低阈值，以实现“提前”加载
        self.check_delay = 50  # 减小延迟，以更频繁检查

        # 自定义颜色
        self.star_color = "red"
        self.tag_bg = "lightgreen"
        self.tag_fg = "black"
        self.actor_fg = "deeppink"
        self.series_fg = "#333333"

        # 主框架：左侧筛选栏，右侧视频网格
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        # 左侧筛选栏（使用Canvas添加滚动条）
        self.left_frame_bg = "#FFD3F0"

        self.filter_canvas = tk.Canvas(
            self.main_frame, width=300, bg=self.left_frame_bg
        )
        self.filter_scrollbar = tk.Scrollbar(
            self.main_frame, orient="vertical", command=self.filter_canvas.yview
        )
        self.filter_inner_frame = tk.Frame(self.filter_canvas, bg=self.left_frame_bg)
        self.filter_inner_frame.bind(
            "<Configure>",
            lambda e: self.filter_canvas.configure(
                scrollregion=self.filter_canvas.bbox("all")
            ),
        )
        self.filter_canvas.create_window(
            (0, 0), window=self.filter_inner_frame, anchor="nw"
        )
        self.filter_canvas.configure(yscrollcommand=self.filter_scrollbar.set)
        self.filter_canvas.pack(side="left", fill="y")
        self.filter_scrollbar.pack(side="left", fill="y")

        # 顶部按钮框架
        top_btn_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        top_btn_frame.pack(pady=5)

        # 刷新按钮
        refresh_btn = tk.Button(
            top_btn_frame,
            text="刷新",
            command=self.refresh_directory,
            bg=self.left_frame_bg,
        )
        refresh_btn.pack(side="left")

        # 多选按钮（原批量编辑）
        self.batch_btn = tk.Button(
            top_btn_frame,
            text="多选",
            command=self.enter_batch_mode,
            bg=self.left_frame_bg,
        )
        self.batch_btn.pack(side="left", padx=5)

        # 编辑所选按钮（初始pack然后forget）
        self.edit_selected_btn = tk.Button(
            self.filter_inner_frame,
            text="编辑所选",
            command=self.edit_selected_videos,
            bg=self.left_frame_bg,
        )
        self.edit_selected_btn.pack(pady=5)
        self.edit_selected_btn.pack_forget()

        # 合并播放按钮（新增），初始隐藏
        self.play_merge_btn = tk.Button(
            self.filter_inner_frame,
            text="合并播放",
            command=self.play_multiple_videos,
            bg=self.left_frame_bg,
        )
        self.play_merge_btn.pack(pady=5)
        self.play_merge_btn.pack_forget()

        # 分开播放按钮，初始隐藏
        self.play_separate_btn = tk.Button(
            self.filter_inner_frame,
            text="分开播放",
            command=self.play_separate_videos,
            bg=self.left_frame_bg,
        )
        self.play_separate_btn.pack(pady=5)
        self.play_separate_btn.pack_forget()

        # 搜索框
        self.search_entry = tk.Entry(self.filter_inner_frame, width=20)
        self.search_entry.pack(pady=5)
        self.search_entry.bind("<Return>", lambda e: self.apply_filters())

        search_btn = tk.Button(
            self.filter_inner_frame,
            text="搜索",
            command=self.apply_filters,
            bg=self.left_frame_bg,
        )
        search_btn.pack(pady=5)

        # 添加灰色横线
        ttk.Separator(self.filter_inner_frame, orient="horizontal").pack(
            fill="x", pady=10
        )

        tk.Label(
            self.filter_inner_frame,
            text="筛选栏",
            font=("Arial", 14, "bold"),
            bg=self.left_frame_bg,
        ).pack(pady=10)

        # 标签选择
        tk.Label(
            self.filter_inner_frame, text="标签筛选（多选）", bg=self.left_frame_bg
        ).pack(pady=5)
        self.tags_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        self.tags_frame.pack(fill="y", expand=False)

        # 演员选择
        actor_header_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        actor_header_frame.pack(pady=5)
        tk.Label(
            actor_header_frame, text="演员筛选（多选）", bg=self.left_frame_bg
        ).pack(side="left")
        self.actor_sort_var = tk.StringVar(value="按影片数量从多到少")
        actor_sort_menu = tk.OptionMenu(
            actor_header_frame,
            self.actor_sort_var,
            "按首字母排序",
            "按最后视频最新发行时间从新到旧",
            "按影片数量从多到少",
            "按影片平均星级从高到低",
            command=lambda v: self.display_filters(),
        )
        actor_sort_menu.pack(side="left", padx=5)
        self.actors_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        self.actors_frame.pack(fill="y", expand=False)

        # 系列选择
        tk.Label(
            self.filter_inner_frame, text="系列筛选（多选）", bg=self.left_frame_bg
        ).pack(pady=5)
        self.series_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        self.series_frame.pack(fill="y", expand=False)

        # 星级选择
        tk.Label(
            self.filter_inner_frame, text="星级筛选（多选）", bg=self.left_frame_bg
        ).pack(pady=5)
        self.ratings_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        self.ratings_frame.pack(fill="y", expand=False)

        # 添加灰色横线
        ttk.Separator(self.filter_inner_frame, orient="horizontal").pack(
            fill="x", pady=10
        )

        # 操作按钮
        ops_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        ops_frame.pack(pady=10)
        reset_btn = tk.Button(
            ops_frame, text="重置", command=self.reset_filters, bg=self.left_frame_bg
        )
        reset_btn.pack(side="left", padx=5)
        undo_btn = tk.Button(
            ops_frame, text="返回上一步", command=self.undo, bg=self.left_frame_bg
        )
        undo_btn.pack(side="left", padx=5)
        redo_btn = tk.Button(
            ops_frame, text="重做下一步", command=self.redo, bg=self.left_frame_bg
        )
        redo_btn.pack(side="left", padx=5)

        # 排序选项
        sort_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        sort_frame.pack(pady=10)
        tk.Label(sort_frame, text="排序", bg=self.left_frame_bg).pack()
        self.sort_var = tk.StringVar(value="从新到旧")
        options = [
            "无",
            "倒序",
            "星级降序",
            "星级升序",
            "演员数量降序",
            "演员数量升序",
            "从新到旧",
            "从旧到新",
            "乱序",
        ]
        sort_menu = tk.OptionMenu(
            sort_frame, self.sort_var, *options, command=lambda v: self.apply_filters()
        )
        sort_menu.pack()

        # 调整界面
        adjust_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        adjust_frame.pack(pady=20, fill="x")
        tk.Label(adjust_frame, text="网格尺寸", bg=self.left_frame_bg).pack()
        self.grid_size_scale = tk.Scale(
            adjust_frame,
            from_=350,
            to=700,
            orient="horizontal",
            command=self.update_sizes,
            resolution=50,
            bg=self.left_frame_bg,
        )
        self.grid_size_scale.set(self.grid_size)
        self.grid_size_scale.pack()
        tk.Label(adjust_frame, text="字体大小", bg=self.left_frame_bg).pack()
        self.font_size_scale = tk.Scale(
            adjust_frame,
            from_=8,
            to=20,
            orient="horizontal",
            command=self.update_sizes,
            bg=self.left_frame_bg,
        )
        self.font_size_scale.set(self.font_size)
        self.font_size_scale.pack()

        # PotPlayer 路径输入
        potplayer_frame = tk.Frame(self.filter_inner_frame, bg=self.left_frame_bg)
        potplayer_frame.pack(pady=20, fill="x")
        tk.Label(potplayer_frame, text="PotPlayer 路径", bg=self.left_frame_bg).pack()
        self.potplayer_entry = tk.Entry(potplayer_frame, width=30)
        self.potplayer_entry.insert(0, self.potplayer_path)
        self.potplayer_entry.pack()
        set_path_btn = tk.Button(
            potplayer_frame,
            text="设置路径",
            command=self.set_potplayer_path,
            bg=self.left_frame_bg,
        )
        set_path_btn.pack(pady=5)

        # 显示缩略图开关
        thumbnail_toggle = tk.Checkbutton(
            self.filter_inner_frame,
            text="显示缩略图",
            variable=self.show_thumbnails,
            command=self.display_videos,
            bg=self.left_frame_bg,
        )
        thumbnail_toggle.pack(pady=10)

        # 右侧滚动画布
        self.canvas = tk.Canvas(self.main_frame)
        self.scrollbar = tk.Scrollbar(
            self.main_frame, orient="vertical", command=self.on_scroll_y
        )
        self.scrollable_frame = tk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # 绑定鼠标滚轮事件
        self.bind_mouse_wheel()

        # 菜单栏
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="选择视频目录", command=self.select_directory)
        filemenu.add_command(label="选项", command=self.open_options)
        filemenu.add_separator()
        filemenu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=filemenu)
        self.root.config(menu=menubar)

    def on_scroll_y(self, *args):
        self.canvas.yview(*args)
        self.schedule_check()

    def set_potplayer_path(self):
        self.potplayer_path = self.potplayer_entry.get().strip()
        messagebox.showinfo("路径更新", "PotPlayer 路径已更新。")

    def bind_mouse_wheel(self):
        def on_mouse_wheel_filter(event):
            direction = int(-1 * (event.delta / 120))
            current_view = self.filter_canvas.yview()
            if direction < 0 and current_view[0] <= 0:
                return
            if direction > 0 and current_view[1] >= 1:
                return
            self.filter_canvas.yview_scroll(direction, "units")

        def on_mouse_wheel_main(event):
            direction = int(-1 * (event.delta / 120))
            current_view = self.canvas.yview()
            if direction < 0 and current_view[0] <= 0:
                return
            if direction > 0 and current_view[1] >= 1:
                return
            self.canvas.yview_scroll(direction, "units")
            self.schedule_check()

        # 递归绑定左侧内帧的所有子部件
        def bind_filter(widget):
            widget.bind("<MouseWheel>", on_mouse_wheel_filter)
            for child in widget.winfo_children():
                bind_filter(child)

        # 递归绑定右侧内帧的所有子部件
        def bind_main(widget):
            widget.bind("<MouseWheel>", on_mouse_wheel_main)
            for child in widget.winfo_children():
                bind_main(child)

        bind_filter(self.filter_inner_frame)
        bind_main(self.scrollable_frame)

        # 也绑定画布本身
        self.filter_canvas.bind("<MouseWheel>", on_mouse_wheel_filter)
        self.canvas.bind("<MouseWheel>", on_mouse_wheel_main)

    def enter_batch_mode(self):
        self.batch_mode = True
        self.batch_btn.config(text="取消多选", command=self.exit_batch_mode)
        self.edit_selected_btn.pack(pady=5)
        self.play_merge_btn.pack(pady=5)
        self.play_separate_btn.pack(pady=5)
        self.display_videos()

    def exit_batch_mode(self):
        self.batch_mode = False
        self.batch_btn.config(text="多选", command=self.enter_batch_mode)
        self.edit_selected_btn.pack_forget()
        self.play_merge_btn.pack_forget()
        self.play_separate_btn.pack_forget()
        self.selected_videos.clear()
        self.display_videos()

    def update_selected(self, path, selected):
        if selected:
            self.selected_videos.add(path)
        else:
            self.selected_videos.discard(path)

    def edit_selected_videos(self):
        if not self.selected_videos:
            messagebox.showinfo("无选择", "请先选择至少一个视频")
            return

        batch_edit_win = tk.Toplevel(self.root)
        batch_edit_win.title("批量编辑视频信息")
        batch_edit_win.geometry("400x500")

        tk.Label(batch_edit_win, text="添加标签 (逗号分隔):").pack()
        add_tags_entry = tk.Entry(batch_edit_win, width=50)
        add_tags_entry.pack()

        self.apply_actors_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            batch_edit_win,
            text="修改演员为 (逗号分隔):",
            variable=self.apply_actors_var,
        ).pack(anchor="w")
        actors_entry = tk.Entry(batch_edit_win, width=50)
        actors_entry.pack()

        self.apply_series_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            batch_edit_win, text="修改系列为:", variable=self.apply_series_var
        ).pack(anchor="w")
        series_entry = tk.Entry(batch_edit_win, width=50)
        series_entry.pack()

        self.apply_release_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            batch_edit_win,
            text="修改发行时间为 (YYYY-MM-DD):",
            variable=self.apply_release_var,
        ).pack(anchor="w")
        release_entry = tk.Entry(batch_edit_win, width=50)
        release_entry.pack()

        self.apply_rating_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            batch_edit_win, text="修改星级为:", variable=self.apply_rating_var
        ).pack(anchor="w")
        rating_var = tk.IntVar(value=1)
        rating_scale = tk.Scale(
            batch_edit_win, from_=1, to=5, orient="horizontal", variable=rating_var
        )
        rating_scale.pack()

        self.apply_feature_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            batch_edit_win, text="修改特征码为:", variable=self.apply_feature_var
        ).pack(anchor="w")
        feature_entry = tk.Entry(batch_edit_win, width=50)
        feature_entry.pack()

        save_btn = tk.Button(
            batch_edit_win,
            text="保存",
            command=lambda: self.save_batch_edits(
                add_tags_entry.get(),
                actors_entry.get(),
                series_entry.get(),
                release_entry.get(),
                rating_var.get(),
                feature_entry.get(),
                batch_edit_win,
            ),
        )
        save_btn.pack(pady=10)

    def save_batch_edits(
        self,
        add_tags_str,
        new_actors_str,
        new_series,
        new_release,
        new_rating,
        new_feature_str,
        win,
    ):
        new_add_tags = [tag.strip() for tag in add_tags_str.split(",") if tag.strip()]
        apply_actors = self.apply_actors_var.get()
        new_actors = (
            [actor.strip() for actor in new_actors_str.split(",") if actor.strip()]
            if apply_actors
            else None
        )
        apply_series = self.apply_series_var.get()
        new_series = new_series.strip() if apply_series and new_series else None
        apply_release = self.apply_release_var.get()
        new_release = new_release.strip() if apply_release and new_release else None
        apply_rating = self.apply_rating_var.get()
        new_rating = new_rating if apply_rating else None
        apply_feature = self.apply_feature_var.get()
        new_feature = new_feature_str.strip() if apply_feature else None

        # 对每个选中的视频进行修改
        for path in list(self.selected_videos):
            # 查找视频信息
            for idx, video in enumerate(self.videos):
                if video[0] == path:
                    # 解包
                    name, tags, actors, series, release, rating, thumbnail, feature = (
                        video[1],
                        video[2].copy(),
                        video[3],
                        video[4],
                        video[5],
                        video[6],
                        video[7],
                        video[8],
                    )
                    # 应用批量修改
                    if new_add_tags:
                        tags.extend(new_add_tags)
                        tags = list(dict.fromkeys(tags))  # 去重但保留顺序
                    if new_actors is not None:
                        actors = new_actors
                    if new_series is not None:
                        series = new_series
                    if new_release is not None:
                        release = new_release
                    if new_rating is not None:
                        rating = new_rating
                    if new_feature is not None:
                        feature = new_feature

                    # 执行重命名保存
                    self.save_edits(
                        path,
                        name,
                        ", ".join(tags),
                        ", ".join(actors),
                        series,
                        release,
                        rating,
                        thumbnail,
                        None,
                        feature,
                    )
                    break

        if win:
            win.destroy()
        self.exit_batch_mode()
        self.refresh_directory()

    def on_canvas_configure(self, event):
        if event.width != self.last_canvas_width:
            self.last_canvas_width = event.width
            self.display_videos()

    def open_options(self):
        options_win = tk.Toplevel(self.root)
        options_win.title("选项")
        options_win.geometry("300x250")
        options_win.grab_set()  # 模态窗口

        # 星级颜色
        tk.Label(options_win, text="星级颜色").pack(pady=5)
        star_btn = tk.Button(
            options_win, text="选择颜色", command=lambda: self.choose_color("star")
        )
        star_btn.pack()

        # 标签背景颜色
        tk.Label(options_win, text="标签背景颜色").pack(pady=5)
        tag_bg_btn = tk.Button(
            options_win, text="选择颜色", command=lambda: self.choose_color("tag_bg")
        )
        tag_bg_btn.pack()

        # 标签文字颜色
        tk.Label(options_win, text="标签文字颜色").pack(pady=5)
        tag_fg_btn = tk.Button(
            options_win, text="选择颜色", command=lambda: self.choose_color("tag_fg")
        )
        tag_fg_btn.pack()

        # 演员名称颜色
        tk.Label(options_win, text="演员名称颜色").pack(pady=5)
        actor_fg_btn = tk.Button(
            options_win, text="选择颜色", command=lambda: self.choose_color("actor_fg")
        )
        actor_fg_btn.pack()

        close_btn = tk.Button(
            options_win, text="关闭", command=lambda: self.close_options(options_win)
        )
        close_btn.pack(pady=10)

    def choose_color(self, color_type):
        color = colorchooser.askcolor()[1]
        if color:
            if color_type == "star":
                self.star_color = color
            elif color_type == "tag_bg":
                self.tag_bg = color
            elif color_type == "tag_fg":
                self.tag_fg = color
            elif color_type == "actor_fg":
                self.actor_fg = color
            self.display_videos()  # 刷新显示

    def close_options(self, win):
        win.destroy()
        self.display_videos()  # 刷新显示

    def select_directory(self):
        self.video_dir = filedialog.askdirectory(title="选择视频目录")
        if self.video_dir:
            self.load_videos()
            self.display_filters()
            self.display_videos()

    def refresh_directory(self):
        if self.video_dir:
            self.load_videos()
            self.display_filters()
            self.display_videos()

    def load_videos(self):
        self.videos = []
        self.all_tags = set()
        self.all_actors = set()
        self.all_series = set()
        self.all_ratings = set()
        self.actor_counts = Counter()
        self.actor_latest_release = defaultdict(lambda: datetime.min)
        self.actor_rating_sums = defaultdict(int)
        self.actor_rating_counts = defaultdict(int)
        for root, _, files in os.walk(self.video_dir):
            for file in files:
                if file.lower().endswith(VIDEO_EXTENSIONS):
                    video_path = os.path.join(root, file)
                    name, tags, actors, series, release, rating, feature = (
                        self.parse_filename(file)
                    )
                    thumbnail = self.find_thumbnail(root, name)
                    self.videos.append(
                        (
                            video_path,
                            name,
                            tags,
                            actors,
                            series,
                            release,
                            rating,
                            thumbnail,
                            feature,
                        )
                    )
                    self.all_tags.update(tags)
                    self.all_actors.update(actors)
                    self.actor_counts.update(actors)
                    if series:
                        self.all_series.add(series)
                    self.all_ratings.add(rating)
                    for actor in actors:
                        if release:
                            try:
                                d = datetime.strptime(release, "%Y-%m-%d")
                                self.actor_latest_release[actor] = max(
                                    self.actor_latest_release[actor], d
                                )
                            except ValueError:
                                pass
                        self.actor_rating_sums[actor] += rating
                        self.actor_rating_counts[actor] += 1

    def parse_filename(self, filename):
        base, ext = os.path.splitext(filename)
        match = re.match(
            r"^(.*?)(?:\[\s*(.*?)\s*\])?(?:\{\s*(.*?)\s*\})?(?:\(\s*(.*?)\s*\))?(?:~\s*(.*?)\s*)?(?:@\s*(\d+)\s*)?(?:%\s*(.*?)\s*)?$",
            base,
        )
        if match:
            name = match.group(1).strip()
            tags_str = match.group(2)
            actors_str = match.group(3)
            series = match.group(4).strip() if match.group(4) else ""
            release = match.group(5).strip() if match.group(5) else ""
            rating_str = match.group(6)
            feature = match.group(7).strip() if match.group(7) else ""
            tags = [
                tag.strip()
                for tag in (tags_str.split(",") if tags_str else [])
                if tag.strip()
            ]
            actors = [
                actor.strip()
                for actor in (actors_str.split(",") if actors_str else [])
                if actor.strip()
            ]
            rating = int(rating_str) if rating_str and rating_str.isdigit() else 1
            rating = max(1, min(5, rating))  # 限制1-5
        else:
            name = base
            tags = []
            actors = []
            series = ""
            release = ""
            rating = 1
            feature = ""
        return name, tags, actors, series, release, rating, feature

    def find_thumbnail(self, root, name):
        for ext in (".jpg", ".png"):
            thumb_path = os.path.join(root + "/cover", f"{name}{ext}")
            if os.path.exists(thumb_path):
                return thumb_path
        return None  # 无封面

    def display_filters(self):
        # 清空标签、演员、系列、星级帧
        for widget in self.tags_frame.winfo_children():
            widget.destroy()
        for widget in self.actors_frame.winfo_children():
            widget.destroy()
        for widget in self.series_frame.winfo_children():
            widget.destroy()
        for widget in self.ratings_frame.winfo_children():
            widget.destroy()

        # 标签
        sorted_tags = sorted(self.all_tags)
        self.tag_vars = {}
        row = 0
        col = 0
        for tag in sorted_tags:
            var = tk.BooleanVar()
            chk = tk.Checkbutton(
                self.tags_frame,
                text=tag,
                variable=var,
                command=self.apply_filters,
                bg=self.left_frame_bg,
            )
            chk.grid(row=row, column=col, sticky="w", padx=5, pady=2)
            self.tag_vars[tag] = var
            col += 1
            if col >= 3:
                col = 0
                row += 1

        # 演员
        sort_option = self.actor_sort_var.get()
        if sort_option == "按首字母排序":
            sorted_actors = sorted(self.all_actors)
        elif sort_option == "按最后视频最新发行时间从新到旧":
            sorted_actors = sorted(
                self.all_actors,
                key=lambda a: self.actor_latest_release[a],
                reverse=True,
            )
        elif sort_option == "按影片数量从多到少":
            sorted_actors = sorted(
                self.all_actors, key=lambda a: self.actor_counts[a], reverse=True
            )
        elif sort_option == "按影片平均星级从高到低":
            sorted_actors = sorted(
                self.all_actors,
                key=lambda a: (
                    self.actor_rating_sums[a] / self.actor_rating_counts[a]
                    if self.actor_rating_counts[a]
                    else 0
                ),
                reverse=True,
            )
        self.actor_vars = {}
        row = 0
        col = 0
        for actor in sorted_actors:
            var = tk.BooleanVar()
            chk = tk.Checkbutton(
                self.actors_frame,
                text=actor,
                variable=var,
                command=self.apply_filters,
                bg=self.left_frame_bg,
            )
            chk.grid(row=row, column=col, sticky="w", padx=5, pady=2)
            self.actor_vars[actor] = var
            col += 1
            if col >= 3:
                col = 0
                row += 1

        # 系列
        sorted_series = sorted(self.all_series)
        self.series_vars = {}
        row = 0
        col = 0
        for series in sorted_series:
            var = tk.BooleanVar()
            chk = tk.Checkbutton(
                self.series_frame,
                text=series,
                variable=var,
                command=self.apply_filters,
                bg=self.left_frame_bg,
            )
            chk.grid(row=row, column=col, sticky="w", padx=5, pady=2)
            self.series_vars[series] = var
            col += 1
            if col >= 3:
                col = 0
                row += 1

        # 星级
        self.rating_vars = {}
        row = 0
        col = 0
        for r in range(1, 6):
            var = tk.BooleanVar()
            chk = tk.Checkbutton(
                self.ratings_frame,
                text=f"{r} 星",
                variable=var,
                command=self.apply_filters,
                bg=self.left_frame_bg,
            )
            chk.grid(row=row, column=col, sticky="w", padx=5, pady=2)
            self.rating_vars[r] = var
            col += 1
            if col >= 3:
                col = 0
                row += 1

        # 重新绑定鼠标滚轮，因为显示过滤器可能添加了新部件
        self.bind_mouse_wheel()

    def save_state(self):
        state = {
            "search_keyword": self.search_keyword,
            "selected_tags": copy.copy(self.selected_tags),
            "selected_actors": copy.copy(self.selected_actors),
            "selected_series": copy.copy(self.selected_series),
            "selected_ratings": copy.copy(self.selected_ratings),
            "sort_option": self.sort_var.get(),
            "current_displayed": (
                copy.deepcopy(self.current_displayed)
                if self.current_displayed
                else None
            ),
        }
        self.history.append(state)
        self.redo_stack.clear()

    def apply_filters(self, save=True):
        if save:
            self.save_state()
        self.search_keyword = self.search_entry.get().strip().lower()
        self.selected_tags = {tag for tag, var in self.tag_vars.items() if var.get()}
        self.selected_actors = {
            actor for actor, var in self.actor_vars.items() if var.get()
        }
        self.selected_series = {
            series for series, var in self.series_vars.items() if var.get()
        }
        self.selected_ratings = {r for r, var in self.rating_vars.items() if var.get()}
        self.display_videos()

    def reset_filters(self):
        self.save_state()
        self.search_entry.delete(0, tk.END)
        for var in self.tag_vars.values():
            var.set(False)
        for var in self.actor_vars.values():
            var.set(False)
        for var in self.series_vars.values():
            var.set(False)
        for var in self.rating_vars.values():
            var.set(False)
        self.sort_var.set("无")
        self.current_displayed = None
        self.apply_filters(save=False)

    def undo(self):
        if self.history:
            state = self.history.pop()
            self.redo_stack.append(
                {
                    "search_keyword": self.search_keyword,
                    "selected_tags": copy.copy(self.selected_tags),
                    "selected_actors": copy.copy(self.selected_actors),
                    "selected_series": copy.copy(self.selected_series),
                    "selected_ratings": copy.copy(self.selected_ratings),
                    "sort_option": self.sort_var.get(),
                    "current_displayed": (
                        copy.deepcopy(self.current_displayed)
                        if self.current_displayed
                        else None
                    ),
                }
            )
            self.restore_state(state)

    def redo(self):
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.history.append(
                {
                    "search_keyword": self.search_keyword,
                    "selected_tags": copy.copy(self.selected_tags),
                    "selected_actors": copy.copy(self.selected_actors),
                    "selected_series": copy.copy(self.selected_series),
                    "selected_ratings": copy.copy(self.selected_ratings),
                    "sort_option": self.sort_var.get(),
                    "current_displayed": (
                        copy.deepcopy(self.current_displayed)
                        if self.current_displayed
                        else None
                    ),
                }
            )
            self.restore_state(state)

    def restore_state(self, state):
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, state["search_keyword"])
        for tag, var in self.tag_vars.items():
            var.set(tag in state["selected_tags"])
        for actor, var in self.actor_vars.items():
            var.set(actor in state["selected_actors"])
        for series, var in self.series_vars.items():
            var.set(series in state["selected_series"])
        for r, var in self.rating_vars.items():
            var.set(r in state["selected_ratings"])
        self.sort_var.set(state["sort_option"])
        self.current_displayed = state.get("current_displayed", None)
        self.apply_filters(save=False)

    def update_sizes(self, value=None):
        self.grid_size = self.grid_size_scale.get()
        self.font_size = self.font_size_scale.get()
        self.display_videos()

    def schedule_check(self):
        if not self.loading_scheduled and self.rendered_count < len(
            self.filtered_videos
        ):
            self.loading_scheduled = True
            self.root.after(self.check_delay, self.perform_check)

    def perform_check(self):
        self.loading_scheduled = False
        view = self.canvas.yview()
        if view[1] > self.scroll_threshold:
            self.load_more_videos()
            self.schedule_check()

    def load_more_videos(self):
        tile_gap = 5
        tile_bg = "#FFFFFF"
        start = self.rendered_count
        end = min(start + self.batch_size, len(self.filtered_videos))
        row = self.current_row
        col = 0
        for i in range(start, end):
            video = self.filtered_videos[i]
            (
                video_path,
                name,
                tags,
                actors,
                series,
                release,
                rating,
                thumbnail,
                feature,
            ) = video
            frame = tk.Frame(
                self.scrollable_frame,
                borderwidth=2,
                relief="flat",
                padx=tile_gap,
                pady=tile_gap,
                width=self.grid_size,
                bg=tile_bg,
                cursor="hand2",
            )
            frame.grid(row=row, column=col, padx=tile_gap, pady=tile_gap, sticky="nsew")
            frame.grid_propagate(False)  # 固定大小
            frame.bind("<Button-1>", lambda e, p=video_path: self.play_video(p))

            # 缩略图（如果启用）
            show_thumb = self.show_thumbnails.get()
            if show_thumb:
                thumb_width = self.grid_size - 2 * tile_gap
                thumb_height = int(thumb_width / 1.5)  # 固定比例
                if thumbnail:
                    thumb_frame = tk.Frame(
                        frame, width=thumb_width, height=thumb_height, bg=tile_bg
                    )
                    thumb_frame.pack_propagate(False)
                    thumb_frame.pack(side="top")
                    thumb_frame.bind(
                        "<Button-1>", lambda e, p=video_path: self.play_video(p)
                    )
                    loading_label = tk.Label(
                        thumb_frame, text="加载中...", bg=tile_bg, anchor="center"
                    )
                    loading_label.pack(fill="both", expand=True)
                    loading_label.bind(
                        "<Button-1>", lambda e, p=video_path: self.play_video(p)
                    )
                    threading.Thread(
                        target=self.load_thumb_thread,
                        args=(
                            thumb_frame,
                            loading_label,
                            thumbnail,
                            thumb_width,
                            thumb_height,
                        ),
                    ).start()
                else:
                    thumb_frame = tk.Frame(
                        frame, width=thumb_width, height=thumb_height, bg=tile_bg
                    )
                    thumb_frame.pack_propagate(False)
                    thumb_frame.pack(side="top")
                    thumb_frame.bind(
                        "<Button-1>", lambda e, p=video_path: self.play_video(p)
                    )
                    placeholder_label = tk.Label(
                        thumb_frame, text="(无封面)", bg=tile_bg, anchor="center"
                    )
                    placeholder_label.pack(fill="both", expand=True)
                    placeholder_label.bind(
                        "<Button-1>", lambda e, p=video_path: self.play_video(p)
                    )

            # 如果在多选模式，显示复选框（放在左上角缩略图区域，避免遮挡底部信息）
            if self.batch_mode:
                check_var = tk.BooleanVar(value=(video_path in self.selected_videos))
                check = tk.Checkbutton(
                    frame,
                    variable=check_var,
                    command=lambda p=video_path, var=check_var: self.update_selected(
                        p, var.get()
                    ),
                )
                check.place(relx=0.02, rely=0.02, anchor="nw")

            # 文字部分向下对齐
            text_frame = tk.Frame(frame, bg=tile_bg)
            text_frame.pack(side="bottom", fill="x")

            # 名称（最多两行，省略号）
            max_chars_per_line = int((self.grid_size - 20) / (self.font_size * 0.6))
            max_chars = max_chars_per_line * 2
            display_name = name
            if len(name) > max_chars:
                display_name = name[: max_chars - 3] + "..."
            name_label = tk.Label(
                text_frame,
                text=display_name,
                font=("Arial", self.font_size, "bold"),
                wraplength=self.grid_size - 20,
                justify="left",
                bg=tile_bg,
            )
            name_label.pack(anchor="w")
            name_label.bind("<Button-1>", lambda e, p=video_path: self.play_video(p))

            # 特征码
            if feature:
                feature_label = tk.Label(
                    text_frame,
                    text=feature,
                    font=("Arial", self.font_size - 2, "italic"),
                    fg="blue",
                    bg=tile_bg,
                )
                feature_label.pack(anchor="w")
                feature_label.bind(
                    "<Button-1>", lambda e, p=video_path: self.play_video(p)
                )

            # 系列
            if series:
                series_text = f"《{series}》"
                series_label = tk.Button(
                    text_frame,
                    text=series_text,
                    fg=self.series_fg,
                    font=("Arial", self.font_size - 2, "underline"),
                    bd=0,
                    bg=tile_bg,
                    activebackground=tile_bg,
                    command=lambda s=series: self.filter_by_series(s),
                )
                series_label.pack(anchor="w")

            # 发行时间
            if release:
                release_label = tk.Label(
                    text_frame,
                    text=release,
                    font=("Arial", self.font_size - 2),
                    bg=tile_bg,
                )
                release_label.pack(anchor="w")
                release_label.bind(
                    "<Button-1>", lambda e, p=video_path: self.play_video(p)
                )

            # 星级显示
            stars = "★" * rating + "☆" * (5 - rating)  # 实心★ 和空心☆
            stars_label = tk.Button(
                text_frame,
                text=stars,
                fg=self.star_color,
                font=("Arial", self.font_size - 2),
                bd=0,
                bg=tile_bg,
                activebackground=tile_bg,
                command=lambda r=rating: self.filter_by_rating(r),
            )
            stars_label.pack(anchor="w")
            stars_label.bind("<Button-1>", lambda e, p=video_path: self.play_video(p))

            # 标签按钮（自定义背景和文字颜色，下划线）
            if tags:
                tags_frame = tk.Frame(text_frame, bg=tile_bg)
                tags_frame.pack(anchor="w")
                for tag in tags:
                    btn = tk.Button(
                        tags_frame,
                        text=tag,
                        bg=self.tag_bg,
                        fg=self.tag_fg,
                        font=("Arial", self.font_size - 2, "underline"),
                        bd=0,
                        command=lambda t=tag: self.filter_by_tag(t),
                    )
                    btn.pack(side="left", padx=2)

            # 演员按钮（下划线，自定义颜色）
            if actors:
                actors_frame = tk.Frame(text_frame, bg=tile_bg)
                actors_frame.pack(anchor="w")
                for actor in actors:
                    btn = tk.Button(
                        actors_frame,
                        text=actor,
                        fg=self.actor_fg,
                        font=("Arial", self.font_size - 2, "underline"),
                        bd=0,
                        bg=tile_bg,
                        activebackground=tile_bg,
                        command=lambda a=actor: self.filter_by_actor(a),
                    )
                    btn.pack(side="left", padx=2)

            # 编辑链接
            edit_label = tk.Label(
                frame,
                text="编辑",
                font=("Arial", self.font_size - 4, "italic underline"),
                fg="gray",
                bg=tile_bg,
            )
            edit_label.place(relx=1.0, rely=1.0, anchor="se")  # 右下角
            edit_label.bind("<Button-1>", lambda e, v=video: self.edit_video(v))

            # 现在绑定右键菜单到整个frame及其子部件
            self.bind_right_click(frame, video)

            col += 1
            if col >= self.cols:
                col = 0
                row += 1

        self.rendered_count = end
        self.current_row = row
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.bind_mouse_wheel()

    def load_thumb_thread(self, thumb_frame, loading_label, path, w, h):
        try:
            img = Image.open(path)
            img.thumbnail((w, h))
            with io.BytesIO() as bio:
                img.save(bio, format="PNG")
                data = bio.getvalue()
            self.root.after(
                0, lambda: self.set_thumb_image(thumb_frame, loading_label, data)
            )
        except Exception:
            self.root.after(0, lambda: loading_label.config(text="(无封面)"))

    def set_thumb_image(self, thumb_frame, loading_label, data):
        photo = ImageTk.PhotoImage(data=data)
        loading_label.config(image=photo, text="")
        loading_label.image = photo

    def display_videos(self):
        # 清空现有内容
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # 如果有自定义显示列表，使用它
        if self.current_displayed is not None:
            self.filtered_videos = self.current_displayed[:]
        else:
            # 正常过滤视频
            self.filtered_videos = []
            for video in self.videos:
                _, name, tags, actors, series, release, rating, _, feature = video
                if self.search_keyword:
                    match = False
                    if self.search_keyword in name.lower():
                        match = True
                    elif any(self.search_keyword in tag.lower() for tag in tags):
                        match = True
                    elif any(self.search_keyword in actor.lower() for actor in actors):
                        match = True
                    elif self.search_keyword in series.lower():
                        match = True
                    if not match:
                        continue
                if self.selected_tags and not self.selected_tags.intersection(tags):
                    continue
                if self.selected_actors and not self.selected_actors.intersection(
                    actors
                ):
                    continue
                if self.selected_series and series not in self.selected_series:
                    continue
                if self.selected_ratings and rating not in self.selected_ratings:
                    continue
                self.filtered_videos.append(video)

        # 排序
        sort_key = None
        reverse = False
        sort_option = self.sort_var.get()
        if sort_option == "星级降序":
            sort_key = lambda v: v[6]
            reverse = True
        elif sort_option == "星级升序":
            sort_key = lambda v: v[6]
            reverse = False
        elif sort_option == "演员数量降序":
            sort_key = lambda v: len(v[3])
            reverse = True
        elif sort_option == "演员数量升序":
            sort_key = lambda v: len(v[3])
            reverse = False
        elif sort_option == "从新到旧":

            def date_key(v):
                try:
                    d = datetime.strptime(v[5], "%Y-%m-%d")
                except:
                    d = None
                if d is None:
                    return datetime.min
                return d

            sort_key = date_key
            reverse = True
        elif sort_option == "从旧到新":

            def date_key(v):
                try:
                    d = datetime.strptime(v[5], "%Y-%m-%d")
                except:
                    d = None
                if d is None:
                    return datetime.max
                return d

            sort_key = date_key
            reverse = False
        elif sort_option == "乱序":
            random.shuffle(self.filtered_videos)
        elif sort_option == "倒序":
            self.filtered_videos.reverse()

        if sort_key:
            self.filtered_videos.sort(key=sort_key, reverse=reverse)

        self.gap_color = "#FFE1F2"  # 瓦片间隙颜色（例如浅灰）
        self.canvas.configure(bg=self.gap_color)  # 右侧大画布背景
        self.scrollable_frame.configure(bg=self.gap_color)  # 实际承载瓦片的 Frame 背景

        # 网格布局：动态列数
        item_width = (
            self.grid_size + 10
        )  # padx=tile_gap, pady=tile_gap, but grid padx= tile_gap
        self.cols = max(1, self.canvas.winfo_width() // item_width)
        self.rendered_count = 0
        self.current_row = 0
        self.load_more_videos()
        # 重置滚动到顶部
        self.canvas.yview_moveto(0)

    def bind_right_click(self, widget, video):
        widget.bind("<Button-3>", lambda e: self.show_menu(e, video))
        for child in widget.winfo_children():
            self.bind_right_click(child, video)

    def show_menu(self, event, video):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="查找相似", command=lambda: self.find_similar(video))
        menu.add_command(label="打开文件夹", command=lambda: self.open_folder(video[0]))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def find_similar(self, video):
        self.save_state()
        self.sort_var.set("无")  # 避免重新排序
        tags_set = set(video[2])
        other_videos = [v for v in self.videos if v[0] != video[0]]
        other_videos.sort(key=lambda v: len(tags_set & set(v[2])), reverse=True)
        similar_videos = other_videos[:15]
        self.current_displayed = similar_videos
        self.display_videos()

    # 在 VideoBrowser 类中，把原来的 open_folder 替换为这个实现
    def open_folder(self, path):
        """
        在资源管理器中打开 path 所在的文件夹并选中该文件。
        使用 ShellExecuteW 调用 explorer.exe /select,"<path>"，更可靠。
        如果失败，则降级为打开所在目录（不选中）。
        """
        try:
            # 规范化并转为绝对路径（确保反斜杠）
            full_path = os.path.abspath(os.path.normpath(path))

            # 构建参数：/select,"C:\path\to\file.ext"
            params = f'/select,"{full_path}"'

            # 使用 ShellExecuteW 调用 explorer，这种方式对引号和 UNC 路径处理更可靠
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "open", "explorer.exe", params, None, 1
            )

            # ShellExecuteW 返回值 > 32 表示成功，其它为错误码
            if isinstance(ret, int) and ret <= 32:
                # 降级：仅打开所在目录（不会选中文件）
                try:
                    os.startfile(os.path.dirname(full_path))
                except Exception as e2:
                    messagebox.showerror("错误", f"无法打开文件夹（备用）：{e2}")
        except Exception as e:
            # 最后兜底：打开所在目录或显示错误
            try:
                os.startfile(os.path.dirname(path))
            except Exception as e2:
                messagebox.showerror(
                    "错误", f"无法打开文件夹: {e}; 备用方式也失败: {e2}"
                )

    def toggle_tag(self, entry, tag):
        current = entry.get().strip()
        tags_list = [t.strip() for t in current.split(",") if t.strip()]
        if tag in tags_list:
            tags_list.remove(tag)
        else:
            tags_list.append(tag)
        new_text = ", ".join(tags_list)
        entry.delete(0, tk.END)
        entry.insert(0, new_text)

    def edit_video(self, video):
        video_path, name, tags, actors, series, release, rating, thumbnail, feature = (
            video
        )
        edit_win = tk.Toplevel(self.root)
        edit_win.title("编辑视频信息")
        edit_win.geometry("400x500")

        tk.Label(edit_win, text="标题:").pack()
        title_entry = tk.Entry(edit_win, width=50)
        title_entry.insert(0, name)
        title_entry.pack()

        tk.Label(edit_win, text="标签 (逗号分隔):").pack()
        tags_entry = tk.Entry(edit_win, width=50)
        tags_entry.insert(0, ", ".join(tags))
        tags_entry.pack()

        # 添加现有标签按钮
        tags_buttons_frame = tk.Frame(edit_win)
        tags_buttons_frame.pack(fill="x", pady=5)
        sorted_tags = sorted(self.all_tags)
        row = 0
        col = 0
        for tag in sorted_tags:
            btn = tk.Button(
                tags_buttons_frame,
                text=tag,
                command=lambda t=tag: self.toggle_tag(tags_entry, t),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="w")
            col += 1
            if col >= 4:
                col = 0
                row += 1

        tk.Label(edit_win, text="演员 (逗号分隔):").pack()
        actors_entry = tk.Entry(edit_win, width=50)
        actors_entry.insert(0, ", ".join(actors))
        actors_entry.pack()

        tk.Label(edit_win, text="系列:").pack()
        series_entry = tk.Entry(edit_win, width=50)
        series_entry.insert(0, series)
        series_entry.pack()

        tk.Label(edit_win, text="发行时间 (YYYY-MM-DD):").pack()
        release_entry = tk.Entry(edit_win, width=50)
        release_entry.insert(0, release)
        release_entry.pack()

        tk.Label(edit_win, text="特征码:").pack()
        feature_entry = tk.Entry(edit_win, width=50)
        feature_entry.insert(0, feature)
        feature_entry.pack()

        tk.Label(edit_win, text="星级 (1-5):").pack()
        rating_var = tk.IntVar(value=rating)
        rating_scale = tk.Scale(
            edit_win, from_=1, to=5, orient="horizontal", variable=rating_var
        )
        rating_scale.pack()

        save_btn = tk.Button(
            edit_win,
            text="保存",
            command=lambda: self.save_edits(
                video_path,
                title_entry.get(),
                tags_entry.get(),
                actors_entry.get(),
                series_entry.get(),
                release_entry.get(),
                rating_var.get(),
                thumbnail,
                edit_win,
                feature_entry.get(),
            ),
        )
        save_btn.pack(pady=10)

        edit_win.update_idletasks()
        req_width = max(400, edit_win.winfo_reqwidth())
        req_height = edit_win.winfo_reqheight()
        edit_win.geometry(f"{req_width}x{req_height}")

    def save_edits(
        self,
        video_path,
        new_name,
        new_tags_str,
        new_actors_str,
        new_series,
        new_release,
        new_rating,
        old_thumbnail,
        win,
        new_feature,
    ):
        new_tags = [tag.strip() for tag in new_tags_str.split(",") if tag.strip()]
        new_actors = [
            actor.strip() for actor in new_actors_str.split(",") if actor.strip()
        ]
        new_release = new_release.strip()
        new_feature = new_feature.strip()

        # 构建新文件名
        base = new_name
        if new_tags:
            base += f"[{', '.join(new_tags)}]"
        if new_actors:
            base += f"{{{', '.join(new_actors)}}}"
        if new_series:
            base += f"({new_series})"
        if new_release:
            base += f"~{new_release}"
        base += f"@{new_rating}"
        if new_feature:
            base += f"%{new_feature}"
        ext = os.path.splitext(video_path)[1]
        new_path = os.path.join(os.path.dirname(video_path), base + ext)

        try:
            os.rename(video_path, new_path)
            # 如果有封面，修改封面名称
            if old_thumbnail:
                try:
                    old_thumb_name, thumb_ext = os.path.splitext(
                        os.path.basename(old_thumbnail)
                    )
                    new_thumb_path = os.path.join(
                        os.path.dirname(old_thumbnail), new_name + thumb_ext
                    )
                    os.rename(old_thumbnail, new_thumb_path)
                except Exception:
                    pass
            if win:
                win.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def filter_by_tag(self, tag):
        self.save_state()
        for t, var in self.tag_vars.items():
            var.set(t == tag)
        self.apply_filters(save=False)

    def filter_by_actor(self, actor):
        self.save_state()
        for a, var in self.actor_vars.items():
            var.set(a == actor)
        self.apply_filters(save=False)

    def filter_by_series(self, series):
        self.save_state()
        for s, var in self.series_vars.items():
            var.set(s == series)
        self.apply_filters(save=False)

    def filter_by_rating(self, rating):
        self.save_state()
        for r, var in self.rating_vars.items():
            var.set(r == rating)
        self.apply_filters(save=False)

    def play_video(self, video_path):
        try:
            subprocess.Popen([self.potplayer_path, video_path])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开 PotPlayer: {e}")

    def play_multiple_videos(self):
        if not self.selected_videos:
            messagebox.showinfo("无选择", "请先选择至少一个视频")
            return
        # 为了保持稳定顺序，按 self.videos 中的顺序排列所选视频
        ordered = [v[0] for v in self.videos if v[0] in self.selected_videos]
        if not ordered:
            messagebox.showinfo("无可播放的视频", "所选的视频在当前列表中未找到")
            return
        try:
            # 使用剪贴板方式添加多个视频到播放列表
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(ordered))
            subprocess.Popen([self.potplayer_path, "/clipboard"])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开 PotPlayer: {e}")

    def play_separate_videos(self):
        if not self.selected_videos:
            messagebox.showinfo("无选择", "请先选择至少一个视频")
            return
        # 为了保持稳定顺序，按 self.videos 中的顺序排列所选视频
        ordered = [v[0] for v in self.videos if v[0] in self.selected_videos]
        if not ordered:
            messagebox.showinfo("无可播放的视频", "所选的视频在当前列表中未找到")
            return
        try:
            for path in ordered:
                subprocess.Popen([self.potplayer_path, path])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开 PotPlayer: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoBrowser(root)
    root.mainloop()

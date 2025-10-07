# Local-video-manager
A lightweight, fully local video management application designed to work with PotPlayer.<br></br>
这是一款轻量的纯本地的视频管理应用。需要结合potplayer使用。

## 特征
- Fully offline — manages local videos without any network functionality
- Convenient browsing and editing of video titles, covers, actors, IDs, series, and years
- Supports custom tags and star ratings
- Filter by tags, ratings, actors, or series
- Supports multiple sorting options
- Supports Chinese / English switching (Menu → File → Options)
<br></br>
- 纯本地应用，本地视频管理，不涉及任何网络功能
- 方便快捷浏览/编辑名称、封面、演员、特征码、系列、年份
- 支持自定义tag、星级
- 支持按tag、星级、演员、系列筛选
- 支持各种排序
- 支持中英文切换（菜单栏 → 文件 → 选项）<br></br>
Note: Color settings, PotPlayer path, and other options are stored in config.json in the root directory.<br></br>
注意：选项中的颜色设置和potplayer路径等信息存储在根目录下的config.json

## 使用
1. Open the application. (either the .py file or the exe in the folder)
2. Go to Menu → File → Select video directory.
3. To add covers, create a folder named cover inside the video directory, and name each cover image file the same as its corresponding video file.
4. Editing: Click the edit button at the bottom-right of a video tile to open the edit window, where you can modify the title, date, tags, series, actors, and rating. After saving, refresh to apply changes.
5. Playback: Set the path to PotPlayer, then click any video tile to play it.
6. Filtering: Use the checkboxes in the left sidebar or click any tag/entry on a video tile to filter videos.
<br></br>
1. 打开应用。(可以用py文件，也可以使用目录下的exe运行)
2. 菜单栏 → 文件 → 选择视频目录
3. 如果要添加封面，请在视频目录下创建“cover”文件夹，并且将封面图片文件命名为对应视频的名称以匹配
4. 编辑功能：点击视频瓦片右下角的编辑按钮呼出编辑窗口，可以编辑名称、日期、tag、系列、演员、星级，保存之后需要刷新才能生效
5. 播放功能：设置potplayer路径，点击视频瓦片进行播放
6. 筛选功能：通过左侧功能栏中的勾选框，或者点击任意瓦片中的词条进行筛选
   

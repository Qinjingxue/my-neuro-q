原项目地址：https://github.com/morettt/my-neuro

基于原项目5.5.6版本进行的修改。

用AIcoding给原项目大改了很多，目前测试3天无严重bug出现。

使用指南：按照原项目5.5.6版本的教程部署后，然后整体用本项目的live-2d-develop文件夹替换掉原项目的live-2d或者live-2d-develop文件夹，和asr_api.py文件。

之后在项目文件夹内打开终端

cd live-2d-develop

npm install jschardet

conda activate my-neuro

python test.py

即可使用

下面是修改内容相关：

debug相关

1 修改了asr-api.py中的模型加载路径，使得路径与按照Readme下载后的默认路径一致

2 修改了test.py，添加一个更新配置前检测模型是否启动的判断，从而修复了在未启动模型时更新配置导致卡顿的bug。并且设置GUI启动时自动读取config.json的TTS语言配置，修复了以前GUI启动时不读取TTS语言配置的bug。

3 修改了start.py，直接npm启动，更简单（AI说启动 Flask 没用，如果有用的话改回原来的版本）

4.添加了npm库jschardet用于解析文件编码，更新了node.js和npm库，electron框架版本

5.修改saveModelPosition()函数，添加边界检查。防止意外拖动模型到屏幕外导致模型消失而需要到config.json手动改回来的bug。

6 取消循环置顶检测，减少CPU占用。

7 增加了切换分辨率时自动适应新的分辨率布局从而保持模型相对屏幕位置不变的功能，防止切换分辨率后模型位置错乱的bug。

功能相关（.js核心文件基本上改完了，ui-controller.js和model-interaction.js基本被翻新了一遍）

2 重构对话框，在live-2d-develop\js\ui下添加了ChatController.js专门用来处理对话框。添加layout.json记录对话框位置

界面更美观，启用快捷键Alt+~可以快速开关对话框输入文本，对话框在改变窗口焦点后会自动隐藏。

由于对话框目前逻辑不需要设置是否展示，设置已经无效，修改了test.py删去了设置文本对话框是否显示的按钮与相关逻辑。

3 增加文件拖拽功能，可以把多个图片或者文本类型文件拖到live2d模型上解析，此时会缓存这些文件，在下一次输入文本或者通过ASR输入语音作为说明后打包在一起发给大模型。

同时修改了自动截图逻辑，拖拽文件缓存后不会触发自动截图，防止意外触发自动截图。

4 重构字幕组件，现在字幕可以直接拖动调整位置和显示范围。

可通过config.json和layout.json的相关设置调整字体大小，颜色，和字幕多长时间自动消失。

5 添加日语逗号作为切分句子的标志，日语句子现在也能正确被切分。

6 增加了热切换ASR开启关闭的功能。

7 增加了一个可以自动停止渲染live2d模型的快捷键。

目前已知bug：由于文件解析功能，导致图片解析出的base64数据会被AI记忆记录，而base64数据过大，导致一旦解析图片数据过多，RAG模块会吃掉巨量显存从而变得不可用。

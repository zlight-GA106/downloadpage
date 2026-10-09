应用图标自动识别目录
====================

把图标文件放在本目录，构建时按 Android 包名自动匹配，匹配到就用它替换默认的字母底板。

命名规则（包名 + 扩展名）：

    com.easycent.app.png
    com.easycent.app.ico
    com.zlight.sendtosmb.png

查找顺序：png -> gif -> ico -> jpg -> jpeg，先命中先用。

建议尺寸 48x48（与页面显示尺寸一致，可避免浏览器缩放发虚）。

关于格式
--------
优先用 PNG 或 GIF。IE6 无法在 <img> 中渲染 .ico，虽然这里认 .ico 文件，
但 IE6 里它会退回显示字母底板；现代浏览器则正常显示。
若要两者都正确，请提供 48x48 的 PNG-8（带透明索引）或 GIF。

新增图标后需要重新构建与发布：

    python tools\build_site.py
    python tools\deploy.py

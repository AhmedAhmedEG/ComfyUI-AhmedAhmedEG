// UI-only translations. Project fields, mode identifiers and user text stay canonical.
const labels = {
  "Project tools": ["项目工具", "أدوات المشروع"],
  "Generate selected shots": ["生成所选镜头", "توليد اللقطات المحددة"],
  "Export with media": ["导出媒体包", "تصدير مع الوسائط"],
  "Import media pack": ["导入媒体包", "استيراد حزمة وسائط"],
  "Recover autosave": ["恢复自动保存", "استعادة الحفظ التلقائي"],
  "New project": ["新建项目", "مشروع جديد"],
  "Continue existing video": ["续接现有视频", "متابعة فيديو موجود"],
  "Shared prompt": ["共享提示词", "الوصف المشترك"],
  "Prompt Forge — draft and review": ["提示词工坊：草稿和审核", "صياغة الأوصاف ومراجعتها"],
  "Create draft": ["生成草稿", "إنشاء مسودة"],
  "Apply reviewed draft": ["应用审核后的草稿", "تطبيق المسودة المراجعة"],
  "Draft unavailable": ["尚无草稿", "لا توجد مسودة"],
  "RefMod library and descriptions": ["RefMod 库与描述", "مكتبة RefMod والأوصاف"],
  "Replace file": ["替换文件", "استبدال الملف"],
  "Remove reference": ["删除参考", "إزالة المرجع"],
  "Reset crop": ["重置裁剪", "إعادة ضبط القص"],
  "Exposure": ["曝光", "التعريض"], "Contrast": ["对比度", "التباين"],
  "Saturation": ["饱和度", "التشبع"], "Scaling": ["缩放", "التحجيم"],
  "Split at playhead": ["在播放位置分割", "تقسيم عند موضع التشغيل"],
  "Equal split": ["等分", "تقسيم متساوٍ"], "Smart split": ["智能分割", "تقسيم ذكي"],
  "Pick frame as reference": ["选取帧作为参考", "اختيار إطار كمرجع"],
  "Upload references": ["上传参考", "رفع المراجع"],
  "Import": ["导入", "استيراد"], "Export": ["导出", "تصدير"],
  "Add Clip": ["添加片段", "إضافة لقطة"], "Add Shot": ["添加镜头", "إضافة لقطة"],
  "Delete": ["删除", "حذف"], "Duplicate": ["复制", "تكرار"],
  "Validate": ["验证", "اعتماد"], "Invalidate": ["取消验证", "إلغاء الاعتماد"],
  "Prompt": ["提示词", "الوصف"], "Duration": ["时长", "المدة"],
  "Selected": ["已选择", "محدد"], "Seed": ["种子", "البذرة"],
  "Audio": ["音频", "الصوت"], "References": ["参考", "المراجع"],
  "Description": ["描述", "الوصف"], "Review": ["审核", "مراجعة"],
  "Left %": ["左 %", "يسار %"], "Top %": ["上 %", "أعلى %"],
  "Width %": ["宽 %", "العرض %"], "Height %": ["高 %", "الارتفاع %"],
};

export function installLocale(root) {
  let language = localStorage.getItem("mmx_director_ui_locale") || "en";
  const original = new WeakMap();
  const translate = () => {
    observer.disconnect();
    for (const element of root.querySelectorAll("button,summary,label,option,span")) {
      for (const child of element.childNodes) {
        if (child.nodeType !== 3) continue;
        const saved = original.get(child);
        // A changed dynamic label becomes its own new original.
        const text = saved && (child.textContent === saved.rendered) ? saved.source : child.textContent;
        const key = text.trim();
        const row = labels[key];
        if (!row) continue;
        const translated = language === "zh" ? row[0] : language === "ar" ? row[1] : key;
        const rendered = text.replace(key, translated);
        child.textContent = rendered; original.set(child, { source: text, rendered });
      }
    }
    observer.observe(root, {childList:true,subtree:true,characterData:true});
  };
  const observer = new MutationObserver(translate);
  observer.observe(root, {childList:true,subtree:true,characterData:true});
  const select = document.createElement("select"); select.title = "UI language";
  select.className = "mmx-language-select";
  for (const [value,label] of [["en","English"],["zh","中文"],["ar","العربية"]]) {
    const option = document.createElement("option"); option.value = value; option.textContent = label; select.appendChild(option);
  }
  select.value = language;
  select.onchange = () => { language = select.value; localStorage.setItem("mmx_director_ui_locale", language); translate(); };
  root.appendChild(select);
  return () => observer.disconnect();
}

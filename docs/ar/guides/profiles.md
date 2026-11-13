---
title: الملفات الشخصية والإعدادات
description: اختر سلوك الأداة أو غيّر أي عتبة فيها.
order: 4
---

# الملفات الشخصية والإعدادات

| الملف | سلوكه |
|---|---|
| `warraq` (الافتراضي) | يقصّ الكتاب حين يكبر نصه 15٪ أو أكثر على الهاتف، أو حين يكون في تصويره عيب (ميل، أشرطة، نص غير متوسط أو متمايل، بقع)؛ هامش 8٪ من عرض النص |
| `reader` | يقصّ كل كتاب يسعه إطار واحد، بهامش 5٪ |
| `eink` | لقرّاء الحبر الإلكتروني: هوامش ضيقة (3٪) وقصّ دائم |
| `crop-only` | يقصّ ولا يدير أي صفحة |

```bash
safha crop book.pdf --profile eink
safha crop book.pdf --set margin=0.05 --set skew_min=0.3
safha profiles -v
```

## ملف إعدادات خاص

```toml
# my.toml
base = "eink"
margin = 0.04
direction = "rtl"
```

```bash
safha crop book.pdf --profile my.toml
```

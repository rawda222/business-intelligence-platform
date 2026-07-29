from pathlib import Path

path = Path(
    "generated/najdi_ffmpeg_work/"
    "reel2_story_branding.ass"
)

brand = (
    "\u0645\u0637\u0639\u0645 "
    "\u0634\u0639\u0628\u064a "
    "\u0646\u062c\u062f\u064a"
)

cta = (
    "\u0627\u0637\u0644\u0628\u0647 "
    "\u0627\u0644\u062d\u064a\u0646 "
    "\u0639\u0628\u0631"
)

apps = (
    "\u062c\u0627\u0647\u0632"
    " - "
    "\u0647\u0646\u0642\u0631\u0633\u062a\u064a\u0634\u0646"
    " - "
    "\u0646\u064a\u0646\u062c\u0627"
)

content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,Tahoma,48,&H00F6E8D5,&H00F6E8D5,&H00150E0B,&HFF000000,-1,0,0,0,100,100,0,0,1,3,1,7,55,55,55,1
Style: CTA,Tahoma,52,&H00FFFFFF,&H00FFFFFF,&H00150E0B,&HFF000000,-1,0,0,0,100,100,0,0,1,3,1,5,60,60,0,1
Style: Apps,Tahoma,43,&H0000D7FF,&H0000D7FF,&H00150E0B,&HFF000000,-1,0,0,0,100,100,0,0,1,3,1,5,55,55,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 5,0:00:00.00,0:00:30.00,Brand,,0,0,0,,{{\\an7\\pos(55,75)\\fad(120,180)}}{brand}
Dialogue: 6,0:00:19.00,0:00:30.00,CTA,,0,0,0,,{{\\an5\\pos(540,1410)\\fad(180,200)}}{cta}
Dialogue: 6,0:00:19.50,0:00:30.00,Apps,,0,0,0,,{{\\an5\\pos(540,1510)\\fad(180,200)}}{apps}
"""

path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

path.write_text(
    content,
    encoding="utf-8",
)

print("ASS_UTF8_RECREATED")
print(brand)
print(cta)
print(apps)

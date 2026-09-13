# -*- coding: utf-8 -*-
"""主窗口卡片网格 · 宽度变化布局回归测试。

用假规则实例化 CleanerApp（不碰真实磁盘、不启动扫描），模拟窗口宽度变化，
检查：
  1. 列数收缩后，多余空列不再占宽（uniform 组残留 bug）
  2. 同一行卡片高度一致（grid_propagate 误用 bug）
  3. 窗口拉伸后卡片自绘描边随新尺寸更新（shell 重绘 3 次上限 bug）

用法：E:\\miniconda3\\python.exe tests/test_layout_resize.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_mod
from app import CleanerApp


def _fake_rules():
    rules = []
    for i in range(12):
        rules.append(dict(
            key=f"fake_{i}", name=f"测试清理项 {i}",
            desc=f"这是第 {i} 个测试规则的描述文本，长度中等一些",
            cat="system", paths=[rf"C:\__not_exist__\{i}"],
            recursive=True, pattern="*",
            default_on=(i % 3 != 0), warn=("需确认后果" if i % 4 == 0 else None),
            _count=10 + i, _size=(i + 1) * 1024 * 1024, _files=[],
        ))
    return rules


class LayoutResizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_build = app_mod.build_rules
        app_mod.build_rules = _fake_rules
        cls.app = CleanerApp()
        # 移到屏幕外并正常映射（withdrawn 不产生真实 Configure 事件）
        cls.app.geometry("+1600+900")
        cls.app.deiconify()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass
        app_mod.build_rules = cls._orig_build

    def _populate(self):
        self.app._sel_state.clear()
        self.app.has_scanned = True
        self.app._apply_visible_rules()
        for _ in range(30):
            self.app.update()

    def _col_widths(self):
        cont = self.app.list_container
        out = []
        for c in range(6):
            x, _y, w, _h = cont.grid_bbox(c, 0)
            if x == 0 and w == 0 and c > 0:
                # grid_bbox 对空列返回 (0,0,0,0) 或 (0,0,1,1)，继续读
                pass
            out.append((c, round(x), round(w)))
        return out

    def _resize(self, w, h=860):
        self.app.geometry(f"{w}x{h}+1600+900")
        for _ in range(30):
            self.app.update()

    def _shell_ok(self):
        """卡片自绘描边 bbox 是否贴合当前卡片尺寸。"""
        bad = []
        for it in self.app.row_widgets:
            card = it["card"]
            cv = card._canvas
            bbox = cv.bbox("card_border")
            if not bbox:
                bad.append((it["rule"]["key"], "no-border"))
                continue
            bw = bbox[2] - bbox[0]
            expect = card.winfo_width() - 4   # INSET 2.0 两侧
            if abs(bw - expect) > 6:
                bad.append((it["rule"]["key"], f"border={bw} card={expect}"))
        return bad

    def _row_height_mismatch(self):
        cols = self.app._cols
        rows = {}
        for idx, it in enumerate(self.app.row_widgets):
            rows.setdefault(idx // cols, []).append(it["card"].winfo_height())
        bad = {}
        for r, hs in rows.items():
            if len(set(hs)) > 1:
                bad[r] = hs
        return bad

    def test_resize_layout(self):
        app = self.app
        # ---- 宽窗口（应 >= 3 列）----
        self._resize(1500)
        self._populate()
        wide_cols = app._cols
        self.assertGreaterEqual(wide_cols, 3, "1500px 宽度下应至少 3 列")
        wide_shell_bad = self._shell_ok()
        self.assertEqual(wide_shell_bad, [], f"宽窗口描边未贴合: {wide_shell_bad}")

        # ---- 收缩到窄窗口（列数应变少）----
        self._resize(1024)
        narrow_cols = app._cols
        self.assertLess(narrow_cols, wide_cols, "1024px 下列数应少于宽窗口")

        # 1) 空列不应再占宽：活跃列之外 cell 宽应为 0
        cont = app.list_container
        for c in range(narrow_cols, 6):
            _x, _y, w, _h = cont.grid_bbox(c, 0)
            self.assertLessEqual(w, 1,
                f"第 {c} 列已停用但仍占宽 {w}px（uniform 残留）")

        # 2) 同一行卡片高度一致
        mismatch = self._row_height_mismatch()
        self.assertEqual(mismatch, {}, f"同行卡片高度参差: {mismatch}")

        # 3) 描边贴合新尺寸
        shell_bad = self._shell_ok()
        self.assertEqual(shell_bad, [], f"收缩后描边未贴合: {shell_bad}")

        # ---- 再拉宽（列数回升）----
        self._resize(1500)
        self.assertEqual(app._cols, wide_cols, "拉宽后列数未恢复")
        mismatch = self._row_height_mismatch()
        self.assertEqual(mismatch, {}, f"拉宽后同行卡片高度参差: {mismatch}")
        shell_bad = self._shell_ok()
        self.assertEqual(shell_bad, [], f"拉宽后描边未贴合: {shell_bad}")

        # ---- 窄窗口下先建卡（首扫场景）：列数应即时正确 ----
        app._cols = 2          # 模拟启动初值 / 上一窗口的旧值
        self._resize(1024)
        self.assertEqual(app._cols, narrow_cols,
                         "未扫描状态下宽度变化未重算列数（影响首扫布局）")


if __name__ == "__main__":
    unittest.main(verbosity=2)

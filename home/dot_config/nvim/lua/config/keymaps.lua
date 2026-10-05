-- Keymaps are automatically loaded on the VeryLazy event

-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here

-- jj to exit insert mode
vim.keymap.set("i", "jj", "<Esc>", { desc = "Exit insert mode" })

-- ファイル操作 (VSCode風)
-- GUI Neovim用
vim.keymap.set("n", "<D-p>", "<cmd>Telescope find_files<cr>", { desc = "ファイル検索 (Cmd+P)" })
vim.keymap.set("n", "<D-S-f>", "<cmd>Telescope live_grep<cr>", { desc = "grep検索 (Cmd+Shift+F)" })
vim.keymap.set("n", "<D-S-e>", function() Snacks.explorer() end, { desc = "エクスプローラー (Cmd+Shift+E)" })
vim.keymap.set("n", "<D-b>", function() Snacks.explorer() end, { desc = "サイドバー (Cmd+B)" })
-- ターミナル用 (Ghostty経由のCSI uシーケンス)
vim.keymap.set("n", "\x1b[101;4u", function() Snacks.explorer() end, { desc = "エクスプローラー (Cmd+Shift+E)" })
vim.keymap.set("n", "\x1b[102;4u", "<cmd>Telescope live_grep<cr>", { desc = "grep検索 (Cmd+Shift+F)" })

-- 保存・閉じる・リロード
vim.keymap.set({ "n", "i", "v" }, "<D-s>", "<cmd>w<cr><esc>", { desc = "保存 (Cmd+S) | vim: :w" })
vim.keymap.set("n", "<D-w>", "<cmd>bd<cr>", { desc = "バッファを閉じる (Cmd+W) | vim: <Space>bd" })
vim.keymap.set("n", "<D-r>", "<cmd>e!<cr>", { desc = "リロード (Cmd+R) | vim: :e!" })

-- 定義ジャンプ
vim.keymap.set("n", "gd", vim.lsp.buf.definition, { desc = "定義へジャンプ | vim: gd (デフォルト)" })

-- コピー＆ペースト (Cmd+C / Cmd+V)
vim.keymap.set("v", "\x1b[99;9u", '"+y', { desc = "コピー (Cmd+C)" })
vim.keymap.set({ "n", "v", "i" }, "\x1b[118;9u", '"+p', { desc = "ペースト (Cmd+V)" })

-- Git
vim.keymap.set("n", "<D-S-g>", function() Snacks.lazygit() end, { desc = "LazyGit (Cmd+Shift+G)" })
vim.keymap.set("n", "\x1b[103;4u", function() Snacks.lazygit() end, { desc = "LazyGit (Cmd+Shift+G)" })

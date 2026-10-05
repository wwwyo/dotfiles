-- markdownlint を nvim から無効化（診断・保存時整形の両方）。
-- 自動生成物(daily/ 配下等)に整形ルールを守らせる意味がなく、ノイズしか出ないため。
-- marksman LSP / render-markdown / prettier 整形は維持する。
return {
  {
    "mfussenegger/nvim-lint",
    optional = true,
    opts = function(_, opts)
      opts.linters_by_ft = opts.linters_by_ft or {}
      opts.linters_by_ft.markdown = {}
      opts.linters_by_ft["markdown.mdx"] = {}
    end,
  },
  {
    "stevearc/conform.nvim",
    optional = true,
    opts = function(_, opts)
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      for _, ft in ipairs({ "markdown", "markdown.mdx" }) do
        local fmts = opts.formatters_by_ft[ft]
        if fmts then
          opts.formatters_by_ft[ft] = vim.tbl_filter(function(f)
            return f ~= "markdownlint-cli2"
          end, fmts)
        end
      end
    end,
  },
  -- ensure_installed から外し、Mason の再インストールを止める
  {
    "mason-org/mason.nvim",
    optional = true,
    opts = function(_, opts)
      opts.ensure_installed = vim.tbl_filter(function(tool)
        return tool ~= "markdownlint-cli2"
      end, opts.ensure_installed or {})
    end,
  },
}

# Data contract

Note: id は変更不可、title は空でない文字列、body と tags は rename で変えない。
rename JSON: {"id":"n1","patch":{"title":"New"}}。未定義の key は誤指定として拒否する。
ローカル data は実行ディレクトリの notes.json のみ。入力値を追加の file path として使わない。
CLI は shell から非対話実行される。未知の note はエラーで、勝手に作成しない。

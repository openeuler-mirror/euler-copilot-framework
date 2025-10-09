{{- define "databases.generateGaussPassword" -}}
  {{- /* 使用确定的特殊字符组合 */ -}}
  {{- $special := "#!" -}}
  
  {{- /* 生成基础密码 */ -}}
  {{- $base := randAlphaNum 10 -}}
  {{- $upper := randAlphaNum 3 | upper -}}
  {{- $digits := randNumeric 3 -}}
  
  {{- /* 组合密码 */ -}}
  {{- $password := print $base $upper $digits $special -}}
  
  {{- /* 转义特殊字符 */ -}}
  {{- $password | replace "!" "\\!" | replace "$" "\\$" | replace "&" "\\&" -}}
{{- end -}}

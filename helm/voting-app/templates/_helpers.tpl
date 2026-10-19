{{- define "voting-app.name" }}voting-app{{- end }}
{{- define "voting-app.labels" }}
app.kubernetes.io/name: {{ include "voting-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end }}
{{- define "voting-app.selectorLabels" }}
app.kubernetes.io/name: {{ include "voting-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
{{- define "voting-app.image" -}}
{{- if not .repository }}{{ fail "image.repository must not be empty" }}{{ end -}}
{{- if not (regexMatch "^[a-f0-9]{40}$" .tag) }}{{ fail "image.tag must be a full 40-character commit SHA" }}{{ end -}}
{{- if not (regexMatch "^sha256:[a-f0-9]{64}$" .digest) }}{{ fail "image.digest must be a sha256 digest" }}{{ end -}}
{{- printf "%s:%s@%s" .repository .tag .digest -}}
{{- end }}
{{- define "voting-app.seccomp" }}
seccompProfile:
  type: RuntimeDefault
{{- end }}
{{- define "voting-app.restricted" }}
allowPrivilegeEscalation: false
capabilities:
  drop: ["ALL"]
readOnlyRootFilesystem: true
{{- end }}
{{- define "voting-app.dbSecretName" -}}
{{- if not (regexMatch "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$" .Values.db.existingSecretName) }}{{ fail "db.existingSecretName must be a DNS label" }}{{ end -}}
{{- .Values.db.existingSecretName -}}
{{- end }}

{{- define "property-triage.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "property-triage.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "property-triage.labels" -}}
helm.sh/chart: {{ include "property-triage.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: ai-property-triage
{{- end }}

{{- define "property-triage.image" -}}
{{- $img := . -}}
{{- printf "%s:%s" $img.repository $img.tag }}
{{- end }}

{{- define "property-triage.namespace" -}}
{{- .Values.namespace }}
{{- end }}

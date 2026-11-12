"""D4 requirement checks for P11, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

KSM = "registry.k8s.io/kube-state-metrics/kube-state-metrics"
LW = ["list", "watch"]

DEFAULT_RESOURCES = [
    ("", ["configmaps", "limitranges", "namespaces", "nodes", "persistentvolumeclaims", "persistentvolumes",
          "pods", "replicationcontrollers", "resourcequotas", "secrets", "services"]),
    ("apps", ["daemonsets", "deployments", "replicasets", "statefulsets"]),
    ("batch", ["cronjobs", "jobs"]),
    ("autoscaling", ["horizontalpodautoscalers"]),
    ("certificates.k8s.io", ["certificatesigningrequests"]),
    ("coordination.k8s.io", ["leases"]),
    ("networking.k8s.io", ["ingresses", "networkpolicies"]),
    ("policy", ["poddisruptionbudgets"]),
    ("storage.k8s.io", ["storageclasses", "volumeattachments"]),
    ("admissionregistration.k8s.io", ["mutatingadmissionpolicies", "mutatingadmissionpolicybindings",
                                      "mutatingwebhookconfigurations", "validatingadmissionpolicies",
                                      "validatingadmissionpolicybindings", "validatingwebhookconfigurations"]),
]


def check(docs):
    c = Checker(docs)
    c.image_deployed("R01-ksm-deployed", KSM)
    c.exposed("R02-main-port-in-cluster", KSM, 8080)
    c.exposed("R03-telemetry-port-in-cluster", KSM, 8081)
    for i, (group, resources) in enumerate(DEFAULT_RESOURCES, start=4):
        c.rbac(f"R{i:02d}-list-watch-{group or 'core'}", KSM, LW, resources, group, cluster_wide=True)
    return c.results

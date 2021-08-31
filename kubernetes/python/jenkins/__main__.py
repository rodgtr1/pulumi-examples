import pulumi
import pulumi_kubernetes as kubernetes
import base64
from pulumi import ResourceOptions
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    ContainerArgs,
    ContainerPortArgs,
    EnvVarArgs,
    EnvVarSourceArgs,
    HTTPGetActionArgs,
    PersistentVolumeClaim,
    PersistentVolumeClaimSpecArgs,
    PodSpecArgs,
    PodTemplateSpecArgs,
    ProbeArgs,
    ResourceRequirementsArgs,
    Secret,
    SecretKeySelectorArgs,
    Service,
    ServiceAccount,
    ServicePortArgs,
    ServiceSpecArgs,
    VolumeArgs,
    VolumeMountArgs,
)
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs

# Get stack name to apply to resources
name=pulumi.get_stack()

config=pulumi.Config()

credentials={
    "username": config.require("username"),
    "password": config.require("password")
}

# Name of one of your Nodes
nodeName='docker-desktop'

# Namespace
namespace="jenkins"

def create_service_account():
    cluster_rule = kubernetes.rbac.v1.ClusterRole(
        name+"-cluster-role",
        api_version="rbac.authorization.k8s.io/v1",
        kind="ClusterRole",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name="jenkins-admin",
        ),
        rules=[
            kubernetes.rbac.v1.PolicyRuleArgs(
                api_groups=[""],
                resources=["*"],
                verbs=["*"],
            )
        ],
    )

    cluster_role_binding = kubernetes.rbac.v1.ClusterRoleBinding(
        name+"_-cluster_role-binding",
        api_version="rbac.authorization.k8s.io/v1",
        kind="ClusterRoleBinding",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name="jenkins-admin",
        ),
        role_ref=kubernetes.rbac.v1.RoleRefArgs(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name="jenkins-admin",
        ),
        subjects=[
            kubernetes.rbac.v1.SubjectArgs(
                kind="ServiceAccount",
                name="jenkins-admin",
                namespace=namespace,
            )
        ],
    )

    admin_service_account = ServiceAccount(
        name+"-service-account",
        api_version="v1",
        kind="ServiceAccount",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name="jenkins-admin",
            namespace=namespace,
        ),
    )
    
def create_secret():
    secret = Secret(
        name+"-secret",
        metadata=ObjectMetaArgs(
            name=name,
            namespace=namespace
        ),
        type="Opaque",
        data={
            "jenkins-username": str(base64.b64encode(bytes(credentials['username'],"utf-8"),None),"utf-8"),
            "jenkins-password": str(base64.b64encode(bytes(credentials["password"],"utf-8"),None),"utf-8"),
        }   
    )

def create_persistent_volume():

    local_storage_storage_class = kubernetes.storage.v1.StorageClass(
        name+"-local-storage-class",
        kind="StorageClass",
        api_version="storage.k8s.io/v1",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name="local-storage",
        ),
        provisioner="kubernetes.io/no-provisioner",
        volume_binding_mode="WaitForFirstConsumer",
    )

    jenkins_pv_volume_persistent_volume = kubernetes.core.v1.PersistentVolume(
        name+"-pv-volume",
        api_version="v1",
        kind="PersistentVolume",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name="jenkins-pv-volume",
            labels={
                "type": "local",
            },
        ),
        spec=kubernetes.core.v1.PersistentVolumeSpecArgs(
            storage_class_name="local-storage",
            claim_ref={
                "name": "jenkins-pv-claim",
                "namespace": namespace,
            },
            capacity={
                "storage": "10Gi",
            },
            access_modes=["ReadWriteOnce"],
            local=kubernetes.core.v1.LocalVolumeSourceArgs(
                path="/mnt",
            ),
            node_affinity={
                "required": {
                    "node_selector_terms": [
                        {
                            "match_expressions": [
                                {
                                    "key": "kubernetes.io/hostname",
                                    "operator": "In",
                                    "values": [nodeName],
                                }
                            ],
                        }
                    ],
                },
            },
        ),
    )

    jenkins_pv_claim_persistent_volume_claim = PersistentVolumeClaim(
        name+"-pv-claim",
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name="jenkins-pv-claim",
            namespace=namespace,
        ),
        spec=PersistentVolumeClaimSpecArgs(
            storage_class_name="local-storage",
            access_modes=["ReadWriteOnce"],
            resources=ResourceRequirementsArgs(
                requests={
                    "storage": "1Gi",
                },
            ),
        ),
    )


def create_deployment():
        
    jenkins_deployment = kubernetes.apps.v1.Deployment(
        name+"-deployment",
        api_version="apps/v1",
        kind="Deployment",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name="jenkins",
            namespace=namespace,
        ),
        spec=kubernetes.apps.v1.DeploymentSpecArgs(
            replicas=1,
            selector=kubernetes.meta.v1.LabelSelectorArgs(
                match_labels={
                    "app": "jenkins-server",
                },
            ),
            template=PodTemplateSpecArgs(
                metadata=kubernetes.meta.v1.ObjectMetaArgs(
                    labels={
                        "app": "jenkins-server",
                    },
                ),
                spec=PodSpecArgs(
                    security_context={
                        "fs_group": 1000,
                        "run_as_user": 1000,
                    },
                    service_account_name="jenkins-admin",
                    containers=[
                        ContainerArgs(
                            name="jenkins",
                            image="bitnami/jenkins",
                            env=[
                                EnvVarArgs(
                                    name="JENKINS_USERNAME",
                                    value_from=EnvVarSourceArgs(
                                        secret_key_ref=SecretKeySelectorArgs(
                                            name=name,
                                            key="jenkins-username",
                                        ),
                                    ),
                                ),
                                EnvVarArgs(
                                    name="JENKINS_PASSWORD",
                                    value_from=EnvVarSourceArgs(
                                        secret_key_ref=SecretKeySelectorArgs(
                                            name=name,
                                            key="jenkins-password",
                                        ),
                                    ),
                                ),
                            ],
                            ports=[
                                ContainerPortArgs(
                                    name="httpport",
                                    container_port=8080,
                                ),
                                ContainerPortArgs(
                                    name="jnlpport",
                                    container_port=50000,
                                ),
                            ],
                            liveness_probe=ProbeArgs(
                                http_get=HTTPGetActionArgs(
                                    path="/login",
                                    port="http",
                                ),
                                initial_delay_seconds=180,
                                timeout_seconds=5,
                                failure_threshold=6,
                            ),
                            readiness_probe=ProbeArgs(
                                http_get=HTTPGetActionArgs(
                                    path="/login",
                                    port="http",
                                ),
                                initial_delay_seconds=90,
                                timeout_seconds=5,
                                period_seconds=6,
                            ),
                            volume_mounts=[
                                {
                                    "name": "jenkins-data",
                                    "mount_path": "/var/jenkins_home",
                                }
                            ],
                        )
                    ],
                    volumes=[
                        VolumeArgs(
                            name="jenkins-data",
                            persistent_volume_claim={
                                "claim_name": "jenkins-pv-claim",
                            },
                        )
                    ],
                ),
            ),
        ),
    )


def create_service():
    jenkins_service_service = Service(
        name+"-service",
        api_version="v1",
        kind="Service",
        metadata=kubernetes.meta.v1.ObjectMetaArgs(
            name="jenkins-service", 
            namespace=namespace
        ),
        spec=ServiceSpecArgs(
            selector={
                "app": "jenkins-server",
            },
            type="NodePort",
            ports=[
                ServicePortArgs(
                    port=8080,
                    target_port=8080,
                    node_port=32000,
                )
            ],
        ),
    )

create_service_account()
create_secret()
create_persistent_volume()
create_deployment()
create_service()

pulumi.export("URL", "http://localhost:32000")

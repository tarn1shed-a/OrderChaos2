import { defineRailway, github, project, service, volume } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "OrderChaos2";
export default defineRailway(() => {
  const data = volume("OrderChaos2-data", {sizeMB: 500, region: "asia-southeast1-eqsg3a"});
  const OrderChaos2 = service("OrderChaos2", {
    source: github("tarn1shed-a/OrderChaos2", { branch: "main", checkSuites: false }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    healthcheck: "/health",
    healthcheckTimeout: 180,
    deploy: {
      restartPolicyType: "ON_FAILURE",
      restartPolicyMaxRetries: 3,
      limitOverride: {containers: {cpu: 2, memoryBytes: 1073741824}},
    },
    // Variables stay unmanaged. Set only the bundle SHA and capacity with the CLI.
    volumeMounts: {"/data": data},
    replicas: { "asia-southeast1-eqsg3a": 1 },
    networking: { privateNetworkEndpoint: "orderchaos2" },
  });

  return project("mellow-endurance", {
    variables: { managed: false },
    resources: [OrderChaos2, data],
  });
});

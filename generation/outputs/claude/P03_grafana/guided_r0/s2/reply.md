```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: grafana-data
  labels:
    app: grafana
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  labels:
    app: grafana
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 472
        runAsGroup: 0
        fsGroup: 472
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: grafana
          image: grafana/grafana:latest
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 3000
              protocol: TCP
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
          readinessProbe:
            tcpSocket:
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 6
          startupProbe:
            tcpSocket:
              port: 3000
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 30
          livenessProbe:
            tcpSocket:
              port: 3000
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 5
          resources:
            requests:
              cpu: 250m
              memory: 750Mi
            limits:
              cpu: "1"
              memory: 1Gi
          volumeMounts:
            - name: grafana-data
              mountPath: /var/lib/grafana
      volumes:
        - name: grafana-data
          persistentVolumeClaim:
            claimName: grafana-data
---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  labels:
    app: grafana
spec:
  type: ClusterIP
  selector:
    app: grafana
  ports:
    - name: http
      port: 3000
      targetPort: 3000
      protocol: TCP
```

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: n8n-secret
  labels:
    app: n8n
type: Opaque
stringData:
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: changePassword
  POSTGRES_DB: n8n
  POSTGRES_NON_ROOT_USER: n8n
  POSTGRES_NON_ROOT_PASSWORD: changeNonRootPassword
  RUNNERS_AUTH_TOKEN: changeRunnerAuthToken
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-init
  labels:
    app: postgres
data:
  init-data.sh: |
    #!/bin/bash
    set -e;

    if [ -n "${POSTGRES_NON_ROOT_USER:-}" ] && [ -n "${POSTGRES_NON_ROOT_PASSWORD:-}" ]; then
    	psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    		CREATE USER ${POSTGRES_NON_ROOT_USER} WITH PASSWORD '${POSTGRES_NON_ROOT_PASSWORD}';
    		GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_NON_ROOT_USER};
    		GRANT CREATE ON SCHEMA public TO ${POSTGRES_NON_ROOT_USER};
    	EOSQL
    else
    	echo "SETUP INFO: No Environment variables given!"
    fi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  labels:
    app: postgres
spec:
  clusterIP: None
  selector:
    app: postgres
  ports:
    - name: postgres
      port: 5432
      targetPort: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  labels:
    app: postgres
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:18
          ports:
            - name: postgres
              containerPort: 5432
          env:
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: POSTGRES_USER
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: POSTGRES_PASSWORD
            - name: POSTGRES_DB
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: POSTGRES_DB
            - name: POSTGRES_NON_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: POSTGRES_NON_ROOT_USER
            - name: POSTGRES_NON_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: POSTGRES_NON_ROOT_PASSWORD
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          securityContext:
            allowPrivilegeEscalation: false
            seccompProfile:
              type: RuntimeDefault
          readinessProbe:
            tcpSocket:
              port: 5432
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 5
            failureThreshold: 10
          startupProbe:
            tcpSocket:
              port: 5432
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 30
          livenessProbe:
            tcpSocket:
              port: 5432
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 6
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
          volumeMounts:
            - name: db-storage
              mountPath: /var/lib/postgresql/data
            - name: init-scripts
              mountPath: /docker-entrypoint-initdb.d
      volumes:
        - name: init-scripts
          configMap:
            name: postgres-init
            defaultMode: 493
  volumeClaimTemplates:
    - metadata:
        name: db-storage
      spec:
        accessModes:
          - ReadWriteOnce
        resources:
          requests:
            storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: n8n-storage
  labels:
    app: n8n
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
---
apiVersion: v1
kind: Service
metadata:
  name: n8n
  labels:
    app: n8n
spec:
  selector:
    app: n8n
  ports:
    - name: http
      port: 5678
      targetPort: 5678
    - name: task-broker
      port: 5679
      targetPort: 5679
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: n8n
  labels:
    app: n8n
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: n8n
  template:
    metadata:
      labels:
        app: n8n
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: n8n
          image: docker.n8n.io/n8nio/n8n:2.43.5
          ports:
            - name: http
              containerPort: 5678
            - name: task-broker
              containerPort: 5679
          env:
            - name: DB_TYPE
              value: postgresdb
            - name: DB_POSTGRESDB_HOST
              value: postgres
            - name: DB_POSTGRESDB_PORT
              value: "5432"
            - name: DB_POSTGRESDB_DATABASE
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: POSTGRES_DB
            - name: DB_POSTGRESDB_USER
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: POSTGRES_NON_ROOT_USER
            - name: DB_POSTGRESDB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: POSTGRES_NON_ROOT_PASSWORD
            - name: N8N_RUNNERS_MODE
              value: external
            - name: N8N_RUNNERS_AUTH_TOKEN
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: RUNNERS_AUTH_TOKEN
            - name: N8N_RUNNERS_BROKER_LISTEN_ADDRESS
              value: 0.0.0.0
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
            seccompProfile:
              type: RuntimeDefault
          readinessProbe:
            tcpSocket:
              port: 5678
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 6
          startupProbe:
            tcpSocket:
              port: 5678
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 30
          livenessProbe:
            tcpSocket:
              port: 5678
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 6
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
          volumeMounts:
            - name: n8n-storage
              mountPath: /home/node/.n8n
      volumes:
        - name: n8n-storage
          persistentVolumeClaim:
            claimName: n8n-storage
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: n8n-runner
  labels:
    app: n8n-runner
spec:
  replicas: 1
  selector:
    matchLabels:
      app: n8n-runner
  template:
    metadata:
      labels:
        app: n8n-runner
    spec:
      containers:
        - name: n8n-runner
          image: n8nio/runners:2.43.5
          env:
            - name: N8N_RUNNERS_AUTH_TOKEN
              valueFrom:
                secretKeyRef:
                  name: n8n-secret
                  key: RUNNERS_AUTH_TOKEN
            - name: N8N_RUNNERS_TASK_BROKER_URI
              value: http://n8n:5679
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
            seccompProfile:
              type: RuntimeDefault
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: "1"
              memory: 1Gi
```

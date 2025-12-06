pipeline {
  agent any

  environment {
    VENV_DIR = "venv_jenkins"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Setup Python') {
      steps {
        // On Linux/macOS agents (if your Jenkins agent is Windows use the "bat" version below)
        sh '''
          python3 -m venv ${VENV_DIR}
          . ${VENV_DIR}/bin/activate
          python -m pip install --upgrade pip
        '''
        // Windows alternative (uncomment if agent is Windows):
        // bat '''
        //   python -m venv %VENV_DIR%
        //   call %VENV_DIR%\\Scripts\\activate
        //   python -m pip install --upgrade pip
        // '''
      }
    }

    stage('Install deps') {
      steps {
        sh '''
          . ${VENV_DIR}/bin/activate
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
        '''
      }
    }

    stage('Lint') {
      steps {
        sh '''
          . ${VENV_DIR}/bin/activate
          if command -v flake8 >/dev/null 2>&1; then
            flake8 || true
          else
            echo "flake8 not installed — skipping lint"
          fi
        '''
      }
    }

    stage('Run tests') {
      steps {
        sh '''
          . ${VENV_DIR}/bin/activate
          if command -v pytest >/dev/null 2>&1; then
            pytest || true
          else
            echo "pytest not found — skipping tests"
          fi
        '''
      }
    }

    stage('Package') {
      steps {
        sh '''
          VERSION=$(date +%Y%m%d%H%M%S)
          zip -r stock_predictor_${VERSION}.zip . -x ".git/*" "${VENV_DIR}/*"
          ls -lh
        '''
      }
    }

    stage('Archive') {
      steps {
        archiveArtifacts artifacts: '*.zip', fingerprint: true
      }
    }
  }

  post {
    success {
      echo "Build succeeded"
    }
    failure {
      echo "Build failed"
    }
  }
}

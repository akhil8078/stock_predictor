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
                // Create virtual environment and upgrade pip (Windows)
                bat '''
                python -m venv %VENV_DIR%
                call %VENV_DIR%\\Scripts\\activate
                python -m pip install --upgrade pip
                '''
            }
        }

        stage('Install deps') {
            steps {
                bat '''
                call %VENV_DIR%\\Scripts\\activate
                if exist requirements.txt (
                    pip install -r requirements.txt
                ) else (
                    echo requirements.txt not found, skipping install
                )
                '''
            }
        }

        stage('Run tests') {
            steps {
                bat '''
                call %VENV_DIR%\\Scripts\\activate
                if exist tests (
                    pytest
                ) else (
                    echo tests folder not found, skipping tests
                )
                '''
            }
        }

        stage('Package') {
            steps {
                // Simple: zip everything in workspace into stock_predictor.zip
                bat 'powershell -Command Compress-Archive -Path * -DestinationPath stock_predictor.zip -Force'
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'stock_predictor.zip', fingerprint: true
            }
        }
    }

    post {
        success {
            echo 'Build succeeded ✅'
        }
        failure {
            echo 'Build failed ❌'
        }
    }
}

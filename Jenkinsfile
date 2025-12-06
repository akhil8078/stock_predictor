pipeline {
    agent any

    environment {
        VENV_DIR = "venv_jenkins"
    }

    stages {
        stage('Checkout') {
            steps {
                // Jenkins already checked out, but this is okay
                checkout scm
            }
        }

        stage('Setup Python') {
            steps {
                // Windows commands -> use 'bat', not 'sh'
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
                // Create a zip of the workspace (excluding venv)
                bat '''
                if exist stock_build rmdir /S /Q stock_build
                mkdir stock_build
                xcopy * stock_build /E /I /Y
                rmdir /S /Q stock_build\\%VENV_DIR%
                powershell -Command "$d = Get-Date -Format yyyyMMddHHmmss; Compress-Archive -Path 'stock_build\\*' -DestinationPath 'stock_predictor_$d.zip' -Force"
                '''
            }
        }

        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'stock_predictor_*.zip', fingerprint: true
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

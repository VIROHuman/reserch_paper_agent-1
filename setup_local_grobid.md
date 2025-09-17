# Setting Up Local GROBID

## Quick Setup (Docker - Recommended)

1. **Start GROBID service:**
   ```bash
   docker-compose -f docker-compose.grobid.yml up -d
   ```

2. **Update your config to use local GROBID:**
   ```python
   # In server/src/config.py
   self.grobid_base_url = "http://localhost:8070"
   ```

3. **Restart your application:**
   ```bash
   python run_server.py
   ```

## Manual Setup (Alternative)

1. **Install Java 11+:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install openjdk-11-jdk
   
   # macOS
   brew install openjdk@11
   
   # Windows
   # Download from Oracle or use Chocolatey
   ```

2. **Download and run GROBID:**
   ```bash
   # Download GROBID
   wget https://github.com/kermitt2/grobid/releases/download/0.8.2/grobid-0.8.2.zip
   unzip grobid-0.8.2.zip
   cd grobid-0.8.2
   
   # Start GROBID service
   ./gradlew run
   ```

3. **Update config and restart your app**

## Performance Comparison

| Setup | Speed | Control | Setup Time | Resource Usage |
|-------|-------|---------|------------|----------------|
| **Cloud** | Medium | Low | 0 minutes | None |
| **Local Docker** | Fast | High | 5 minutes | 2-4GB RAM |
| **Local Manual** | Fast | High | 30 minutes | 2-4GB RAM |

## Recommended: Start with Cloud

For immediate testing and development, use the cloud service. Upgrade to local GROBID when you need:
- Higher throughput
- Better performance
- Offline processing
- Custom configurations


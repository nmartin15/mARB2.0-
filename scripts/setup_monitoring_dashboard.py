#!/usr/bin/env python3
"""Setup script for monitoring dashboards."""
import os
import sys
import json
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def create_dashboard_directory() -> Path:
    """Create monitoring dashboard directory."""
    dashboard_dir = project_root / "monitoring"
    dashboard_dir.mkdir(exist_ok=True)
    return dashboard_dir


def create_html_dashboard(api_url: str, dashboard_dir: Path) -> Path:
    """Create HTML monitoring dashboard."""
    dashboard_file = dashboard_dir / "dashboard.html"
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mARB 2.0 - Monitoring Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }}
        
        .header h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        
        .header p {{
            color: #666;
        }}
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .card {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        .card h2 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.2em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .status {{
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
        }}
        
        .status.healthy {{
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }}
        
        .status.unhealthy {{
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }}
        
        .status.degraded {{
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }}
        
        .metric {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        
        .metric:last-child {{
            border-bottom: none;
        }}
        
        .metric-label {{
            color: #666;
            font-weight: 500;
        }}
        
        .metric-value {{
            color: #333;
            font-weight: bold;
            font-size: 1.1em;
        }}
        
        .component-list {{
            list-style: none;
        }}
        
        .component-list li {{
            padding: 8px 0;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .component-list li:last-child {{
            border-bottom: none;
        }}
        
        .component-status {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        
        .component-status.healthy {{
            background: #d4edda;
            color: #155724;
        }}
        
        .component-status.unhealthy {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .refresh-info {{
            text-align: center;
            color: #666;
            font-size: 0.9em;
            margin-top: 20px;
        }}
        
        .links {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 15px;
        }}
        
        .link-button {{
            display: inline-block;
            padding: 8px 16px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.9em;
            transition: background 0.3s;
        }}
        
        .link-button:hover {{
            background: #5568d3;
        }}
        
        .error-message {{
            color: #721c24;
            background: #f8d7da;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
        }}
        
        .loading {{
            text-align: center;
            color: #666;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 mARB 2.0 Monitoring Dashboard</h1>
            <p>Real-time system health and performance metrics</p>
            <div class="links">
                <a href="{api_url}/docs" target="_blank" class="link-button">API Docs</a>
                <a href="{api_url}/api/v1/health/detailed" target="_blank" class="link-button">Health JSON</a>
                <a href="{api_url}/api/v1/cache/stats" target="_blank" class="link-button">Cache Stats</a>
            </div>
        </div>
        
        <div class="dashboard-grid">
            <div class="card">
                <h2>System Health</h2>
                <div id="status" class="loading">Loading...</div>
            </div>
            
            <div class="card">
                <h2>Cache Performance</h2>
                <div id="metrics" class="loading">Loading...</div>
            </div>
            
            <div class="card">
                <h2>Component Status</h2>
                <div id="components" class="loading">Loading...</div>
            </div>
        </div>
        
        <div class="refresh-info">
            Auto-refreshing every 30 seconds | Last updated: <span id="last-update">-</span>
        </div>
    </div>
    
    <script>
        const API_BASE = '{api_url}/api/v1';
        
        async function fetchHealth() {{
            try {{
                const response = await fetch(`${{API_BASE}}/health/detailed`);
                if (!response.ok) {{
                    throw new Error(`HTTP ${{response.status}}`);
                }}
                const data = await response.json();
                updateStatus(data);
                updateComponents(data);
                updateLastUpdate();
            }} catch (error) {{
                document.getElementById('status').innerHTML = 
                    '<div class="status unhealthy">Error fetching health status: ' + error.message + '</div>';
                document.getElementById('components').innerHTML = 
                    '<div class="error-message">Unable to load component status</div>';
            }}
        }}
        
        async function fetchCacheStats() {{
            try {{
                const response = await fetch(`${{API_BASE}}/cache/stats`);
                if (!response.ok) {{
                    throw new Error(`HTTP ${{response.status}}`);
                }}
                const data = await response.json();
                updateMetrics(data);
            }} catch (error) {{
                document.getElementById('metrics').innerHTML = 
                    '<div class="error-message">Unable to load cache statistics: ' + error.message + '</div>';
            }}
        }}
        
        function updateStatus(data) {{
            const statusDiv = document.getElementById('status');
            const statusClass = data.status === 'healthy' ? 'healthy' : 
                              data.status === 'degraded' ? 'degraded' : 'unhealthy';
            statusDiv.innerHTML = `
                <div class="status ${{statusClass}}">
                    <h3 style="margin-bottom: 10px;">System Status: ${{data.status.toUpperCase()}}</h3>
                    <p><strong>Version:</strong> ${{data.version}}</p>
                    <p><strong>Timestamp:</strong> ${{new Date(data.timestamp).toLocaleString()}}</p>
                </div>
            `;
        }}
        
        function updateComponents(data) {{
            const componentsDiv = document.getElementById('components');
            if (!data.components || Object.keys(data.components).length === 0) {{
                componentsDiv.innerHTML = '<p>No component data available</p>';
                return;
            }}
            
            let html = '<ul class="component-list">';
            for (const [name, comp] of Object.entries(data.components)) {{
                const statusClass = comp.status === 'healthy' ? 'healthy' : 'unhealthy';
                const responseTime = comp.response_time_ms ? ` (${{comp.response_time_ms}}ms)` : '';
                const workers = comp.active_workers ? ` (${{comp.active_workers}} workers)` : '';
                html += `
                    <li>
                        <span><strong>${{name.charAt(0).toUpperCase() + name.slice(1)}}</strong></span>
                        <span class="component-status ${{statusClass}}">${{comp.status}}${{responseTime}}${{workers}}</span>
                    </li>
                `;
                if (comp.error) {{
                    html += `<li style="color: #721c24; font-size: 0.85em; padding-left: 20px;">${{comp.error}}</li>`;
                }}
            }}
            html += '</ul>';
            componentsDiv.innerHTML = html;
        }}
        
        function updateMetrics(data) {{
            const metricsDiv = document.getElementById('metrics');
            if (!data.overall) {{
                metricsDiv.innerHTML = '<p>No cache statistics available</p>';
                return;
            }}
            
            const hitRate = (data.overall.hit_rate * 100).toFixed(2);
            const total = data.overall.hits + data.overall.misses;
            metricsDiv.innerHTML = `
                <div class="metric">
                    <span class="metric-label">Cache Hits</span>
                    <span class="metric-value">${{data.overall.hits.toLocaleString()}}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Cache Misses</span>
                    <span class="metric-value">${{data.overall.misses.toLocaleString()}}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Requests</span>
                    <span class="metric-value">${{total.toLocaleString()}}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Hit Rate</span>
                    <span class="metric-value" style="color: ${{hitRate > 70 ? '#155724' : hitRate > 50 ? '#856404' : '#721c24'}}">${{hitRate}}%</span>
                </div>
            `;
        }}
        
        function updateLastUpdate() {{
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        }}
        
        // Initial load
        fetchHealth();
        fetchCacheStats();
        
        // Refresh every 30 seconds
        setInterval(() => {{
            fetchHealth();
            fetchCacheStats();
        }}, 30000);
    </script>
</body>
</html>
"""
    
    dashboard_file.write_text(html_content)
    return dashboard_file


def create_nginx_config(dashboard_dir: Path) -> str:
    """Generate nginx configuration snippet for serving dashboard."""
    config = f"""
# Add this to your nginx configuration to serve the monitoring dashboard
location /monitoring {{
    alias {dashboard_dir};
    index dashboard.html;
    
    # Optional: Add basic authentication for production
    # auth_basic "Monitoring Dashboard";
    # auth_basic_user_file /etc/nginx/.htpasswd;
    
    # Optional: Restrict access to specific IPs
    # allow 192.168.1.0/24;
    # deny all;
}}
"""
    return config


def main():
    """Main setup function."""
    print("=" * 70)
    print("mARB 2.0 - Monitoring Dashboard Setup")
    print("=" * 70)
    print()
    
    # Get API URL
    api_url = os.getenv("API_URL", "http://localhost:8000")
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        user_input = input(f"Enter API URL (default: {api_url}): ").strip()
        if user_input:
            api_url = user_input
    
    # Ensure URL doesn't end with /
    api_url = api_url.rstrip('/')
    
    print(f"Using API URL: {api_url}")
    print()
    
    # Create dashboard directory
    print("Creating monitoring dashboard directory...")
    dashboard_dir = create_dashboard_directory()
    print(f"✓ Created directory: {dashboard_dir}")
    print()
    
    # Create HTML dashboard
    print("Creating HTML monitoring dashboard...")
    dashboard_file = create_html_dashboard(api_url, dashboard_dir)
    print(f"✓ Created dashboard: {dashboard_file}")
    print()
    
    # Generate nginx config
    nginx_config = create_nginx_config(dashboard_dir)
    nginx_config_file = dashboard_dir / "nginx.conf.snippet"
    nginx_config_file.write_text(nginx_config)
    print(f"✓ Created nginx config snippet: {nginx_config_file}")
    print()
    
    # Summary
    print("=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)
    print()
    print("Your monitoring dashboard has been created!")
    print()
    print("Next steps:")
    print()
    print("1. Test the dashboard locally:")
    print(f"   cd {dashboard_dir}")
    print("   python -m http.server 8080")
    print("   Then visit: http://localhost:8080/dashboard.html")
    print()
    print("2. For production, add to nginx configuration:")
    print(f"   See: {nginx_config_file}")
    print()
    print("3. Optional: Set up Flower for Celery monitoring:")
    print("   celery -A app.services.queue.tasks flower --port=5555")
    print("   Then visit: http://localhost:5555")
    print()
    print("4. Optional: Configure Sentry for error tracking:")
    print("   See: SENTRY_SETUP_CHECKLIST.md")
    print()
    print("Dashboard file location:")
    print(f"   {dashboard_file}")
    print()


if __name__ == "__main__":
    main()


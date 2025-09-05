#!/bin/bash

# Voice Agent Scaling Script
# Usage: ./scale.sh [up|down|status] [replicas]

set -e

DOCKER_COMPOSE_FILE="docker-compose.yml"
DEFAULT_REPLICAS=10
MAX_REPLICAS=20

function usage() {
    echo "Usage: $0 [up|down|status|test] [replicas]"
    echo ""
    echo "Commands:"
    echo "  up [replicas]     - Scale up agent workers (default: $DEFAULT_REPLICAS)"
    echo "  down              - Scale down all services"
    echo "  status            - Show current scaling status"
    echo "  test              - Run system health tests"
    echo ""
    echo "Examples:"
    echo "  $0 up             # Scale to default replicas"
    echo "  $0 up 15          # Scale to 15 agent workers"
    echo "  $0 status         # Show current status"
    echo "  $0 test           # Run health checks"
}

function check_requirements() {
    if ! command -v docker-compose &> /dev/null; then
        echo "Error: docker-compose is required but not installed."
        exit 1
    fi
    
    if ! command -v curl &> /dev/null; then
        echo "Error: curl is required but not installed."
        exit 1
    fi
    
    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        echo "Error: $DOCKER_COMPOSE_FILE not found in current directory."
        exit 1
    fi
    
    if [ ! -f ".env" ]; then
        echo "Warning: .env file not found. Please copy env.template to .env and configure."
    fi
}

function scale_up() {
    local replicas=${1:-$DEFAULT_REPLICAS}
    
    if [ "$replicas" -gt "$MAX_REPLICAS" ]; then
        echo "Warning: Requested replicas ($replicas) exceeds recommended maximum ($MAX_REPLICAS)"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    echo "Scaling voice agent system..."
    echo "Target agent workers: $replicas"
    
    # Start core services first
    echo "Starting core services (Redis, Orchestrator)..."
    docker-compose up -d redis orchestrator
    
    # Wait for core services to be ready
    echo "Waiting for core services to be ready..."
    sleep 10
    
    # Check orchestrator health
    for i in {1..30}; do
        if curl -s http://localhost:8080/health > /dev/null 2>&1; then
            echo "Orchestrator is ready"
            break
        fi
        echo "Waiting for orchestrator... ($i/30)"
        sleep 2
    done
    
    # Start monitoring
    echo "Starting monitoring services..."
    docker-compose up -d prometheus grafana nginx
    
    # Scale agent workers
    echo "Starting $replicas agent workers..."
    for i in $(seq 1 $replicas); do
        if [ $i -le 10 ]; then
            docker-compose up -d agent-worker-$i
        else
            # For more than 10 workers, we'd need to generate additional services
            echo "Note: Only 10 pre-configured workers available. For more workers, modify docker-compose.yml"
            break
        fi
    done
    
    echo "Scaling complete!"
    echo ""
    show_status
}

function scale_down() {
    echo "Scaling down all services..."
    docker-compose down
    echo "All services stopped."
}

function show_status() {
    echo "=== Voice Agent System Status ==="
    echo ""
    
    # Docker containers status
    echo "Container Status:"
    docker-compose ps
    echo ""
    
    # Service health checks
    echo "Service Health Checks:"
    
    # Check orchestrator
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "✓ Orchestrator: Healthy"
        
        # Get detailed stats
        if command -v jq &> /dev/null; then
            stats=$(curl -s http://localhost:8080/stats 2>/dev/null | jq -r '.active_rooms // 0')
            queue=$(curl -s http://localhost:8080/stats 2>/dev/null | jq -r '.queue_length // 0')
            echo "  - Active rooms: $stats"
            echo "  - Queue length: $queue"
        fi
    else
        echo "✗ Orchestrator: Unhealthy"
    fi
    
    # Check Redis
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo "✓ Redis: Healthy"
    else
        echo "✗ Redis: Unhealthy"
    fi
    
    # Check Prometheus
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo "✓ Prometheus: Healthy"
    else
        echo "✗ Prometheus: Unhealthy"
    fi
    
    # Check Grafana
    if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "✓ Grafana: Healthy"
    else
        echo "✗ Grafana: Unhealthy"
    fi
    
    echo ""
    echo "Access URLs:"
    echo "  - Orchestrator API: http://localhost:8080"
    echo "  - Orchestrator Health: http://localhost:8080/health"
    echo "  - Orchestrator Stats: http://localhost:8080/stats"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000 (admin/admin)"
    echo "  - Load Balancer: http://localhost:80"
}

function run_tests() {
    echo "=== Running System Health Tests ==="
    echo ""
    
    # Test orchestrator endpoints
    echo "Testing orchestrator endpoints..."
    
    if curl -s -f http://localhost:8080/health > /dev/null; then
        echo "✓ Health endpoint: OK"
    else
        echo "✗ Health endpoint: FAILED"
    fi
    
    if curl -s -f http://localhost:8080/stats > /dev/null; then
        echo "✓ Stats endpoint: OK"
    else
        echo "✗ Stats endpoint: FAILED"
    fi
    
    # Test manual dispatch
    echo ""
    echo "Testing manual agent dispatch..."
    test_room="test-$(date +%s)"
    
    if curl -s -X POST "http://localhost:8080/manual/dispatch?room=$test_room&participant_identity=test-user" > /dev/null; then
        echo "✓ Manual dispatch: OK"
    else
        echo "✗ Manual dispatch: FAILED"
    fi
    
    # Test metrics endpoints
    echo ""
    echo "Testing metrics collection..."
    
    if curl -s http://localhost:8080/metrics | grep -q "webhook_requests_total"; then
        echo "✓ Orchestrator metrics: OK"
    else
        echo "✗ Orchestrator metrics: FAILED"
    fi
    
    echo ""
    echo "System tests completed."
}

# Main script execution
case "${1:-}" in
    "up")
        check_requirements
        scale_up "$2"
        ;;
    "down")
        check_requirements
        scale_down
        ;;
    "status")
        check_requirements
        show_status
        ;;
    "test")
        check_requirements
        run_tests
        ;;
    *)
        usage
        exit 1
        ;;
esac

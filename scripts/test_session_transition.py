#!/usr/bin/env python3
"""
Test automatico transizione sessione con timer→0

Simula esattamente il comportamento reale:
- Carica savegame
- Attende timer sessione → 0
- Verifica transizione automatica
- Verifica emit SocketIO (tramite flag)
"""

import json
import os
import sys
import time
from pathlib import Path

# Setup path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python_backend'))

os.environ['FLASK_ENV'] = 'testing'

from flask import Flask
from flask_socketio import SocketIO
from utils.weekend_orchestrator import WeekendOrchestrator, WeekendSessionType, WeekendSessionState
from utils.session_bridge import SessionBridge
from models import Pilota, Team


class SessionTransitionTester:
    """Testa transizione automatica quando timer→0"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test-secret'
        self.socketio = SocketIO(self.app, cors_allowed_origins='*')
        
        self.orchestrator = None
        self.bridge = None
        self.session_ended_events = []
        
        # Setup callback SocketIO
        @self.socketio.on('connect')
        def on_connect():
            print("🔌 SocketIO connected")
        
        @self.socketio.on('session_ended')
        def on_session_ended(data):
            print(f"📩 SESSION_ENDED received: {data}")
            self.session_ended_events.append(data)
    
    def create_minimal_savegame(self, session_type=WeekendSessionType.FP1):
        """Crea savegame minimale per test"""
        save_data = {
            'save_id': 'test_transition',
            'save_name': 'Test Transition',
            'circuit': 'jp-1962_suzuka',
            'session_type': session_type.value,
            'session_time_remaining': 10.0,  # 10 secondi
            'cars': [],
            'teams': [],
            'drivers': [],
            'weekend_state': {
                'current_session': session_type.value,
                'session_state': 'running',
                'sessions_completed': []
            }
        }
        
        save_path = PROJECT_ROOT / 'python_backend' / 'saves' / 'test_transition.json'
        save_path.parent.mkdir(exist_ok=True)
        
        with open(save_path, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"💾 Savegame creato: {save_path}")
        return save_path
    
    def setup_test_session(self):
        """Setup sessione test"""
        print("\n" + "="*60)
        print("🧪 TEST: Transizione automatica timer→0")
        print("="*60)
        
        # Crea savegame
        save_path = self.create_minimal_savegame()
        
        # Carica savegame
        with open(save_path, 'r') as f:
            save_data = json.load(f)
        
        # Inizializza orchestrator
        self.orchestrator = WeekendOrchestrator()
        self.orchestrator.start(
            circuit_id='jp-1962_suzuka',
            session_type=WeekendSessionType(save_data['session_type'])
        )
        
        # Inizializza bridge
        self.bridge = SessionBridge(
            app=self.app,
            socketio=self.socketio,
            orchestrator=self.orchestrator,
            save_data=save_data,
            cars=[],
            is_quick_race=False
        )
        
        print(f"✅ Setup completato: {save_data['session_type']}")
        print(f"   Timer iniziale: {save_data['session_time_remaining']}s")
        
        return save_data
    
    def simulate_timer_countdown(self, initial_time=10.0, dt=0.1):
        """Simula countdown timer fino a 0"""
        print(f"\n⏱️  Simulo countdown: {initial_time}s → 0s")
        
        elapsed = 0.0
        while True:
            # Tick bridge
            self.bridge.tick(dt)
            elapsed += dt
            
            # Check tempo rimanente
            time_remaining = self.bridge.session_time_remaining
            
            if elapsed % 2.0 < dt:  # Log ogni 2 secondi
                print(f"   ⏱️  {elapsed:5.1f}s elapsed | time_remaining: {time_remaining:5.1f}s | state: {self.orchestrator.current_state.value}")
            
            # Check se sessione finita
            if hasattr(self.bridge, '_session_just_ended') and self.bridge._session_just_ended:
                print(f"\n🎯 SESSION ENDED DETECTED!")
                print(f"   From: {self.bridge._session_ended_from}")
                print(f"   To: {self.bridge._session_ended_to}")
                print(f"   Flag: {self.bridge._session_just_ended}")
                return True
            
            # Timeout sicurezza
            if elapsed > 30.0:  # Max 30 secondi
                print(f"\n❌ TIMEOUT: transizione non rilevata dopo {elapsed}s")
                return False
        
        return False
    
    def verify_transition(self):
        """Verifica transizione completata"""
        print("\n" + "="*60)
        print("📋 VERIFICA TRANSIZIONE")
        print("="*60)
        
        # Check stato orchestrator
        current_state = self.orchestrator.current_state
        current_session = self.orchestrator.current_session
        
        print(f"Stato corrente: {current_state.value}")
        print(f"Sessione corrente: {current_session.value}")
        
        # Verifica avanzamento
        if current_state == WeekendSessionState.NEXT_SESSION:
            print("✅ TRANSIZIONE COMPLETATA: NEXT_SESSION")
            return True
        else:
            print(f"❌ TRANSIZIONE FALLITA: stato = {current_state.value}")
            return False
    
    def run_test(self):
        """Esegui test completo"""
        print("\n" + "="*60)
        print("🚀 SESSION TRANSITION AUTOMATIC TEST")
        print("="*60)
        
        # Setup
        save_data = self.setup_test_session()
        
        # Simula countdown
        transition_detected = self.simulate_timer_countdown(
            initial_time=save_data['session_time_remaining']
        )
        
        # Verifica
        transition_completed = self.verify_transition()
        
        # Report
        print("\n" + "="*60)
        print("📊 TEST REPORT")
        print("="*60)
        print(f"Transizione rilevata: {'✅ YES' if transition_detected else '❌ NO'}")
        print(f"Transizione completata: {'✅ YES' if transition_completed else '❌ NO'}")
        print(f"SocketIO events: {len(self.session_ended_events)}")
        
        if self.session_ended_events:
            for event in self.session_ended_events:
                print(f"   📩 {event}")
        
        # Cleanup
        save_path = PROJECT_ROOT / 'python_backend' / 'saves' / 'test_transition.json'
        if save_path.exists():
            save_path.unlink()
            print(f"\n🗑️  Savegame test eliminato")
        
        # Exit code
        success = transition_detected and transition_completed
        print(f"\n{'✅ TEST PASSED' if success else '❌ TEST FAILED'}")
        
        return success


def main():
    """Main entry point"""
    tester = SessionTransitionTester()
    success = tester.run_test()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

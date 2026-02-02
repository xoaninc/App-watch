"""Enrich one existing alert for testing purposes."""
import asyncio
import sys
sys.path.insert(0, '/var/www/renfeserver')

from core.database import SessionLocal
from src.gtfs_bc.realtime.infrastructure.models.alert import AlertModel
from src.gtfs_bc.realtime.infrastructure.services.ai_alert_classifier import AIAlertClassifier

async def main():
    db = SessionLocal()
    try:
        # Get one alert from Renfe C1
        alert = db.query(AlertModel).filter(
            AlertModel.alert_id.like('RENFE_%')
        ).first()
        
        if not alert:
            print("❌ No Renfe alerts found")
            return
            
        print(f"📝 Alert: {alert.alert_id}")
        print(f"   Header: {alert.header_text}")
        print(f"   Description: {alert.description_text[:100]}...")
        
        # Enrich with AI
        print("\n🤖 Enriching with Groq AI...")
        from core.config import settings as app_settings
        classifier = AIAlertClassifier(settings=app_settings)
        analysis = classifier.analyze_single_alert(
            alert_id=alert.alert_id,
            description_text=alert.description_text or "",
            header_text=alert.header_text or ""
        )
        
        print(f"\n✅ AI Analysis:")
        print(f"   Severity: {analysis.severity}")
        print(f"   Status: {analysis.status}")
        print(f"   Reason: {analysis.reason}")
        print(f"   Line Open: {analysis.is_line_open}")
        print(f"   Affected: {analysis.affected_segments}")
        
        # Update DB
        from datetime import datetime
        alert.ai_severity = analysis.severity
        alert.ai_status = analysis.status
        alert.ai_summary = analysis.reason  # reason is the summary
        alert.ai_affected_segments = str(analysis.affected_segments) if analysis.affected_segments else None
        alert.ai_processed_at = datetime.utcnow()
        
        db.commit()
        print("\n💾 Alert updated in database")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())

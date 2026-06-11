
"""
Lance tous les tests unitaires. Double-clic ou F5.
"""
import sys, os, unittest
 
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
unittest.TextTestRunner(verbosity=2).run(
    unittest.TestLoader().discover("tests", pattern="test_*.py")
)
 
input("\nEntrée pour fermer...")
 
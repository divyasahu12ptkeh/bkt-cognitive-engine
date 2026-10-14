import unittest
from math_engine import BKTEngine

class TestBKTEngine(unittest.TestCase):
    def setUp(self):
        self.engine = BKTEngine(p_init=0.1, p_transit=0.15, p_slip=0.1, p_guess=0.2)

    def test_asymptotic_convergence(self):
        """10 consecutive correct answers should drive mastery toward 0.99+ asymptotically."""
        p = self.engine.p_init
        for _ in range(10):
            p = self.engine.update_mastery(p, correct=True)
        self.assertGreater(p, 0.95)
        self.assertLess(p, 1.0)

    def test_slip_penalty(self):
        """An incorrect answer must lower mastery without zeroing it out."""
        p_high = 0.85
        p_dropped = self.engine.update_mastery(p_high, correct=False)
        self.assertLess(p_dropped, p_high)
        self.assertGreater(p_dropped, 0.0)

    def test_retrievability_decay(self):
        """At t=0, retention is 1.0; as t increases, retention strictly decreases."""
        s = 100.0
        self.assertAlmostEqual(self.engine.retrievability(0, s), 1.0)
        self.assertLess(self.engine.retrievability(50, s), 1.0)
        self.assertAlmostEqual(self.engine.retrievability(self.engine.time_to_forget(s, 0.7), s), 0.7, places=4)

if __name__ == "__main__":
    unittest.main()
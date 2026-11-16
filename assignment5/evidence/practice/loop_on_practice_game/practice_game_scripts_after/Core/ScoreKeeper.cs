using UnityEngine;

/// <summary>The run's score.</summary>
public class ScoreKeeper : MonoBehaviour
{
    public int Score { get; private set; }

    public void Add(int points)
    {
        Score += points;
    }
}

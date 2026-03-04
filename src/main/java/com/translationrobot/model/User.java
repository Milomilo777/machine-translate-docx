package com.translationrobot.model;

import jakarta.persistence.*;
import java.util.Objects;
import java.util.UUID;

/**
 * Represents a user of the translation robot system.
 */
@Entity
@Table(name = "users")
public class User {

    @Id
    @Column(name = "id", updatable = false, nullable = false, columnDefinition = "BINARY(16)")
    private UUID id;

    @Column(name = "username", nullable = false, unique = true, length = 50)
    private String username;

    @Column(name = "email", nullable = false, unique = true, length = 100)
    private String email;

    @Column(name = "role", nullable = false, length = 20) // Consider an enum for roles in future iterations
    private String role;

    /**
     * Default constructor for JPA.
     */
    public User() {
        // JPA requires a no-arg constructor
    }

    /**
     * Constructor for creating a new User instance.
     * Generates a UUID for the ID.
     *
     * @param username The unique username.
     * @param email The unique email address.
     * @param role The user's role (e.g., "ADMIN", "USER").
     */
    public User(String username, String email, String role) {
        this.id = UUID.randomUUID(); // Application-level UUID generation
        this.username = username;
        this.email = email;
        this.role = role;
    }

    // --- Getters and Setters ---
    public UUID getId() {
        return id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    // --- Equals and HashCode ---
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        User user = (User) o;
        return Objects.equals(id, user.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }

    // --- ToString ---
    @Override
    public String toString() {
        return "User{" +
               "id=" + id +
               ", username='" + username + '\'' +
               ", email='" + email + '\'' +
               ", role='" + role + '\'' +
               '}';
    }
}
